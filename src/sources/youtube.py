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

    def __init__(self, config: Dict[str, Any], target_db: float = REFERENCE_DB):
        super().__init__(config)
        self.timeout = config.get("timeout", 60)
        self.max_duration = int(config.get("max_duration", 600))
        self.target_db = target_db

    # ------------------------------------------------------------------ recherche

    @staticmethod
    def _keyword(media_type: str) -> str:
        return "main theme soundtrack" if media_type == "movie" else "tv series theme song"

    def _ydl(self):
        import yt_dlp   # importé à la demande : l'appli démarre même si le module manque
        return yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "socket_timeout": self.timeout,
                                 "noplaylist": True, "skip_download": True, "extract_flat": False})

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

    def candidates(self, title: str, media_type: str = "series", limit: int = 6) -> List[Dict[str, Any]]:
        """Résultats classés ; même forme que AnimeThemes (un « groupe » par vidéo, avec un lecteur YouTube)."""
        entries = [e for e in self._raw_search(f"{title} {self._keyword(media_type)}", 8)
                   if _ID_RE.match(str(e.get("id", "")))]
        entries.sort(key=lambda e: -self._score(title, e))
        out = []
        for e in entries[:limit]:
            dur = int(e.get("duration") or 0)
            out.append({"name": e.get("title", "?"), "year": f"{dur // 60}:{dur % 60:02d}" if dur else "",
                        "channel": e.get("uploader") or e.get("channel") or "",
                        "score": max(0, min(100, int(self._score(title, e)))),
                        "themes": [{"slug": "▶", "type": "yt", "youtube": e["id"], "url": watch_url(e["id"])}]})
        return out

    def search(self, title: str, media_type: str = "series") -> Optional[ThemeResult]:
        """Meilleur résultat pour le mode automatique (None si rien de convaincant)."""
        for c in self.candidates(title, media_type, limit=1):
            if c["score"] >= 40:
                return ThemeResult(title=c["name"], source=self.name, url=c["themes"][0]["url"])
        return None

    @staticmethod
    def is_allowed_url(url: str) -> bool:
        return bool(_URL_RE.match(url or ""))

    # ------------------------------------------------------------------ téléchargement

    def download(self, url: str, output_path: Path) -> bool:
        if not self.is_allowed_url(url):
            return False
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[YouTube] Téléchargement : %s", url)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                import yt_dlp
                opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": self.timeout,
                        "format": "bestaudio/best", "outtmpl": str(Path(tmp) / "source.%(ext)s"),
                        "match_filter": yt_dlp.utils.match_filter_func(f"duration <= {self.max_duration}")}
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                logger.error("[YouTube] Téléchargement impossible : %s", e)
                return False
            files = sorted(Path(tmp).glob("source.*"))
            if not files:
                logger.error("[YouTube] Aucun fichier reçu (vidéo trop longue ou refusée)")
                return False
            out = Path(tmp) / "theme.mp3"
            if not convert_to_mp3(files[0], out, self.target_db):
                return False
            shutil.move(str(out), str(output_path))
        logger.info("[YouTube] ✅ Enregistré : %s", output_path)
        return True
