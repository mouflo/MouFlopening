"""
Source YouTube (via yt-dlp) pour les séries et les films non japonais, absents d'AnimeThemes.

- Recherche : « <titre> <mot-clé> » ; on écoute chaque résultat dans la page (lecteur YouTube intégré)
- Téléchargement : on ne garde que l'audio, converti en MP3 normalisé (comme AnimeThemes)
"""

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..fsutil import safe_move
from ..progress import say
from .. import ytcookies
from .base_source import BaseSource, ThemeResult
from ..audio import REFERENCE_DB, convert_to_mp3
from ..matching import similarity

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[\w-]{11}$")
_URL_RE = re.compile(r"^https://(?:www\.)?youtube\.com/watch\?v=([\w-]{11})$")
# Mots qui rendent un résultat plus probable (générique) ou moins probable (reprise, réaction…)
_GOOD = ("theme", "opening", "intro", "main title", "générique", "generique", "soundtrack", "ost", "title sequence")
_BAD = ("reaction", "réaction", "cover", "remix", "lyrics", "karaoke", "tutorial", "piano", "guitar", "10 hours", "1 hour", "episode", "trailer", "review")


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


class YouTubeSource(BaseSource):
    name = "YouTube"
    _good_clients = None      # profil de lecteur qui a fonctionné en dernier (mémorisé tant que l'appli tourne)

    def __init__(self, config: Dict[str, Any], target_db: float = REFERENCE_DB):
        super().__init__(config)
        self.timeout = config.get("timeout", 60)
        self.max_duration = int(config.get("max_duration", 600))
        self.target_db = target_db
        self.last_error = ""

    # ------------------------------------------------------------------ recherche

    @staticmethod
    def _keywords(media_type: str) -> List[str]:
        """Plusieurs formulations : comme à la main (« die hard 2 theme »), une seule ne suffit pas"""
        if media_type == "movie":
            return ["theme", "main theme", "soundtrack", "OST", "bande originale", "main title"]
        return ["theme", "theme song", "intro", "opening", "générique", "soundtrack"]

    def _ydl(self):
        import yt_dlp   # importé à la demande : l'appli démarre même si le module manque
        return yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "socket_timeout": self.timeout,
                                 "noplaylist": True, "skip_download": True, "extract_flat": "in_playlist"})   # liste rapide (titre, durée, chaîne)

    def _raw_search(self, query: str, count: int) -> List[Dict[str, Any]]:
        try:
            with self._ydl() as ydl:
                info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
            return [e for e in (info or {}).get("entries", []) if e]
        except Exception as e:
            logger.error("[YouTube] Recherche impossible : %s", e)
            return []

    def _score(self, title: str, entry: Dict[str, Any]) -> float:
        name = (entry.get("title") or "").lower()
        score = similarity(title, entry.get("title") or "") / 4      # le titre cherché doit apparaître
        if title.lower() in name:
            score += 40
        score += 15 * sum(w in name for w in _GOOD[:6])
        score -= 30 * sum(w in name for w in _BAD)
        dur = entry.get("duration") or 0
        if dur and dur > self.max_duration:
            score -= 100
        elif 20 <= dur <= 240:
            score += 15
        return score

    def _upload_years(self, entries: List[Dict[str, Any]]) -> None:
        """Ajoute `_year` (année de mise en ligne) aux entrées : la recherche rapide ne donne pas la date."""
        from concurrent.futures import ThreadPoolExecutor

        def one(e):
            if e.get("upload_date"):
                e["_year"] = int(str(e["upload_date"])[:4])
                return
            try:
                import yt_dlp
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True,
                                       "socket_timeout": 15, "noplaylist": True}) as ydl:
                    info = ydl.extract_info(watch_url(e["id"]), download=False)
                if info and info.get("upload_date"):
                    e["_year"] = int(str(info["upload_date"])[:4])
            except Exception:
                pass                                       # pas de date : aucune pénalité
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(one, entries))

    def candidates(self, title: str, media_type: str = "series", limit: int = 10, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """Résultats classés ; même forme que AnimeThemes (un « groupe » par vidéo, avec un lecteur YouTube).
        year : année de sortie du film / de la série. Une vidéo mise en ligne bien avant n'a aucun rapport : elle est écartée."""
        from concurrent.futures import ThreadPoolExecutor
        queries = [f"{title} {k}" for k in self._keywords(media_type)]
        if year:
            queries += [f"{title} {year} theme", f"{title} {year} soundtrack"]
        say(f"YouTube : {len(queries)} recherches en parallèle…")
        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            batches = list(pool.map(lambda q: self._raw_search(q, 8), queries))
        say(f"YouTube : {sum(len(b) for b in batches)} vidéos reçues, tri par pertinence…")
        seen, entries = set(), []
        for batch in batches:                      # sans doublon, en gardant l'ordre de pertinence de YouTube
            for e in batch:
                vid = str(e.get("id", ""))
                if _ID_RE.match(vid) and vid not in seen:
                    seen.add(vid)
                    entries.append(e)
        entries.sort(key=lambda e: -self._score(title, e))
        entries = entries[:max(limit * 2, 14)]
        if year:
            say(f"Vérification des dates de mise en ligne (film de {year})…")
            self._upload_years(entries)
            for e in entries:
                u = e.get("_year")
                if u:
                    e["_bonus"] = 5 if u >= year - 1 else -70   # un thème ne peut pas dater d'avant le film (1 an de marge : bande-annonce)
        entries.sort(key=lambda e: -(self._score(title, e) + e.get("_bonus", 0)))
        out = []
        for e in entries[:limit]:
            dur = int(e.get("duration") or 0)
            label = f"{dur // 60}:{dur % 60:02d}" if dur else ""
            if e.get("_year"):
                label = f"{label} · {e['_year']}" if label else str(e["_year"])
            out.append({"name": e.get("title", "?"), "year": label,
                        "channel": e.get("uploader") or e.get("channel") or "",
                        "score": max(0, min(100, int(self._score(title, e) + e.get("_bonus", 0)))),
                        "themes": [{"slug": "▶", "type": "yt", "youtube": e["id"], "url": watch_url(e["id"])}]})
        return out

    def search(self, title: str, media_type: str = "series", year: Optional[int] = None) -> Optional[ThemeResult]:
        """Meilleur résultat pour le mode automatique (None si rien de convaincant)."""
        for c in self.candidates(title, media_type, limit=1, year=year):
            if c["score"] >= 40:
                return ThemeResult(title=c["name"], source=self.name, url=c["themes"][0]["url"])
        return None

    @staticmethod
    def is_allowed_url(url: str) -> bool:
        return bool(_URL_RE.match(url or ""))

    @staticmethod
    def canonical_url(url: str) -> str:
        """Lien YouTube sous toutes ses formes (youtu.be, shorts, m., music., &t=, &list=…) -> https://youtube.com/watch?v=ID. Autre lien : inchangé."""
        from urllib.parse import urlparse, parse_qs
        try:
            u = urlparse((url or "").strip())
            host = (u.hostname or "").lower()
            vid = ""
            if host == "youtu.be":
                vid = u.path.strip("/").split("/")[0]
            elif host == "youtube.com" or host.endswith(".youtube.com"):
                if u.path.startswith(("/shorts/", "/embed/", "/live/")):
                    vid = u.path.split("/")[2]
                else:
                    vid = (parse_qs(u.query).get("v") or [""])[0]
            if re.fullmatch(r"[\w-]{11}", vid or ""):
                return watch_url(vid)
        except (ValueError, IndexError):
            pass
        return (url or "").strip()

    # ------------------------------------------------------------------ téléchargement

    def _yt_download(self, url: str, tmp: str, clients=None, max_duration=None) -> str:
        """Télécharge l'audio dans tmp ; retourne « » si OK, sinon le message d'erreur.
        clients : autres « profils » de lecteur YouTube à essayer quand le profil par défaut est refusé."""
        try:
            import yt_dlp
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": self.timeout,
                    "format": "bestaudio/best", "outtmpl": str(Path(tmp) / "source.%(ext)s"),
                    "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {max_duration or self.max_duration}"), **ytcookies.opts()}
            def hook(d):
                if d.get("status") == "downloading":
                    tot = d.get("total_bytes") or d.get("total_bytes_estimate")
                    if tot and d.get("downloaded_bytes") is not None:
                        pct = int(100 * d["downloaded_bytes"] / tot)
                        if pct >= self._last_pct + 10 or pct == 100:
                            self._last_pct = pct
                            say(f"Téléchargement depuis YouTube : {pct} %")
            self._last_pct = -10
            opts["progress_hooks"] = [hook]
            if clients:
                opts["extractor_args"] = {"youtube": {"player_client": list(clients)}}
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return ""
        except Exception as e:
            return str(e)

    def _probe_duration(self, url: str) -> int:
        """Durée de la vidéo en secondes (0 si inconnue) : sert à expliquer un refus « trop longue »."""
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": self.timeout, **ytcookies.opts()}) as ydl:
                return int((ydl.extract_info(url, download=False) or {}).get("duration") or 0)
        except Exception:
            return 0

    def download(self, url: str, output_path: Path, trusted: bool = False, any_url: bool = False) -> bool:
        """trusted : vidéo choisie par la communauté (ThemerrDB) — on accepte une durée plus longue (25 min au lieu de 10)."""
        md = max(self.max_duration, 1500) if trusted else self.max_duration
        self.last_error = ""
        if not any_url and not self.is_allowed_url(url):
            logger.error("[YouTube] Lien refusé : %s", url)
            self.last_error = "lien non reconnu (colle un lien YouTube de type youtube.com/watch?v=…)"
            return False
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_error = ""
        logger.info("[YouTube] Téléchargement : %s", url)
        say("Connexion à YouTube…")
        with tempfile.TemporaryDirectory() as tmp:
            err = self._yt_download(url, tmp, self._good_clients, md)       # le profil qui a marché la dernière fois d'abord
            if err and _looks_outdated(err):
                say("YouTube a refusé : mise à jour de yt-dlp…")
                if _upgrade_ytdlp():
                    err = self._yt_download(url, tmp, None, md)      # avec la version à jour
                if err and _looks_outdated(err):           # YouTube refuse parfois un profil de lecteur mais pas les autres
                    for clients in (("tv", "web_safari"), ("mweb", "ios"), ("web_embedded", "android")):
                        logger.info("[YouTube] Nouvel essai avec le profil %s", "+".join(clients))
                        say(f"YouTube a refusé : nouvel essai avec un autre profil ({'+'.join(clients)})…")
                        err = self._yt_download(url, tmp, clients, md)
                        if not err:
                            YouTubeSource._good_clients = clients      # on s'en souvient pour les prochains téléchargements
                            break
            if err:
                try:
                    import yt_dlp
                    logger.error("[YouTube] (yt-dlp version %s)", yt_dlp.version.__version__)
                except Exception:
                    pass
            if err:
                logger.error("[YouTube] Téléchargement impossible : %s", err)
                self.last_error = _friendly(err)
                return False
            files = sorted(Path(tmp).glob("source.*"))
            if not files:
                dur = self._probe_duration(url)
                if dur and dur > md:
                    logger.error("[YouTube] Vidéo de %d min, limite %d min", dur // 60, md // 60)
                    self.last_error = f"vidéo de {dur // 60} min : trop longue pour un thème (limite {md // 60} min)"
                else:
                    logger.error("[YouTube] Aucun fichier reçu (durée %s s)", dur or "inconnue")
                    self.last_error = "YouTube n'a fourni aucun fichier pour cette vidéo : choisis-en une autre"
                return False
            say(f"Conversion en MP3 et réglage du volume ({self.target_db:g} dB)…")
            out = Path(tmp) / "theme.mp3"
            if not convert_to_mp3(files[0], out, self.target_db):
                return False
            safe_move(out, output_path)
        logger.info("[YouTube] ✅ Enregistré : %s", output_path)
        return True


# ---------------------------------------------------------------------------
# YouTube change souvent : quand yt-dlp est trop ancien (erreur 403, « Sign in »…), on le met à jour tout seul
# ---------------------------------------------------------------------------

_last_upgrade = 0.0


def _friendly(err: str) -> str:
    e = err.lower()
    if "not available" in e or "unavailable" in e or "private video" in e or "removed" in e:
        return "YouTube refuse ce téléchargement depuis le serveur (la vidéo marche peut-être dans ton navigateur) : réessaie dans quelques minutes ou choisis-en une autre"
    if "sign in" in e or "age" in e and "restrict" in e:
        return "YouTube demande une connexion pour cette vidéo : choisis-en une autre"
    if "claimed content" in e or "blocked" in e or "copyright" in e:
        return "YouTube bloque cette vidéo (droits d'auteur / pays) : impossible de la télécharger, cherche une autre version à la main"
    if "403" in e or "forbidden" in e:
        return "YouTube a refusé le téléchargement (403) : réessaie dans quelques minutes"
    if "duration" in e or "does not pass filter" in e:
        return "vidéo trop longue pour un thème : choisis-en une plus courte"
    return "téléchargement impossible (détails : bouton Journal)"


def _looks_outdated(err: str) -> bool:
    e = err.lower()
    return any(k in e for k in ("403", "forbidden", "sign in to confirm", "unable to extract", "nsig", "signature", "http error 4",
                                "not available", "unavailable", "requested format", "player response"))


def _upgrade_ytdlp(force: bool = False) -> bool:
    """Met yt-dlp à jour (au plus une fois toutes les 6 h, sauf force). Retourne True si la mise à jour a réussi."""
    global _last_upgrade
    import subprocess
    import sys
    import time
    if not force and time.time() - _last_upgrade < 6 * 3600:
        return False
    _last_upgrade = time.time()
    try:
        logger.info("[YouTube] Mise à jour de yt-dlp…")
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp"],
                           capture_output=True, text=True, timeout=240)
        if r.returncode != 0:
            logger.error("[YouTube] Mise à jour de yt-dlp impossible : %s", (r.stderr or r.stdout).strip()[-300:])
            return False
        for name in [m for m in sys.modules if m == "yt_dlp" or m.startswith("yt_dlp.")]:
            del sys.modules[name]                  # rechargé à la prochaine utilisation
        import importlib
        importlib.invalidate_caches()
        logger.info("[YouTube] yt-dlp mis à jour")
        return True
    except Exception as e:
        logger.error("[YouTube] Mise à jour de yt-dlp impossible : %s", e)
        return False


def auto_update_loop(is_busy, first_delay=60, every=24 * 3600):
    """Met yt-dlp à jour tout seul au démarrage puis chaque jour (YouTube change souvent, yt-dlp suit).
    On attend qu'aucun lot ne tourne pour ne pas gêner un téléchargement en cours."""
    import time
    time.sleep(first_delay)
    while True:
        while is_busy():
            time.sleep(300)
        try:
            _upgrade_ytdlp(force=True)
        except Exception as e:
            logger.error("[YouTube] Mise à jour automatique de yt-dlp en erreur : %s", e)
        time.sleep(every)
