"""
Source AnimeThemes - API publique (sans compte ni clé) pour les génériques d'anime.

Documentation de l'API : https://api-docs.animethemes.moe
"""

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from ..fsutil import safe_move
from .base_source import BaseSource, ThemeResult
from ..audio import REFERENCE_DB, convert_to_mp3
from ..matching import similarity

logger = logging.getLogger(__name__)

# Une seule requête ramène l'anime, ses titres alternatifs, ses thèmes et le lien audio
INCLUDES = "animesynonyms,animethemes.animethemeentries.videos.audio"


class AnimeThemesSource(BaseSource):
    """Source AnimeThemes (https://animethemes.moe)"""

    name = "AnimeThemes"

    def __init__(self, config: Dict[str, Any], threshold: int = 70, target_db: float = REFERENCE_DB):
        super().__init__(config)
        self.api_url = config.get("api_url", "https://api.animethemes.moe").rstrip("/")
        self.timeout = config.get("timeout", 30)
        # Ordre de préférence : le générique d'ouverture d'abord, puis la fin
        self.theme_types: List[str] = config.get("theme_types", ["OP", "ED"])
        self.threshold = config.get("threshold", threshold)
        self.target_db = target_db
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "User-Agent": "MouFlopening/0.2"})

    # ------------------------------------------------------------------ recherche

    def search(self, title: str, media_type: str = "auto") -> Optional[ThemeResult]:
        """Cherche le meilleur générique pour un titre d'anime."""
        if media_type in ("movie", "tv"):
            # AnimeThemes ne contient que des animes ; on laisse les autres sources s'en charger
            logger.debug("[AnimeThemes] type %s ignoré", media_type)
            return None

        logger.info("[AnimeThemes] Recherche : %s", title)
        self.api_error = False
        animes = self._query_animes(title)
        best, score = self._best_anime(title, animes)
        if not best:
            logger.info("[AnimeThemes] Aucun anime assez proche de « %s »", title)
            return None

        theme = self._pick_theme(best)
        if not theme:
            logger.info("[AnimeThemes] « %s » n'a aucun générique avec audio", best["name"])
            return None

        slug, audio_url, video_url = theme
        return ThemeResult(
            title=f"{best['name']} - {slug}",
            source=self.name,
            url=audio_url or video_url,
            quality="audio" if audio_url else "video",
            metadata={"anime": best["name"], "slug": slug, "score": score, "video_url": video_url},
        )

    def candidates(self, title: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Plusieurs animes proches du titre, avec tous leurs génériques (pour choisir à l'oreille)."""
        out = []
        for anime in self._query_animes(title):
            names = [anime.get("name", "")] + [s.get("text", "") for s in anime.get("animesynonyms", [])]
            score = max((similarity(title, n) for n in names if n), default=0)
            themes = []
            for theme in sorted(anime.get("animethemes", []), key=lambda t: (t.get("type") != "OP", t.get("sequence") or 1)):
                found = self._first_link(theme)
                if found:
                    themes.append({"slug": theme.get("slug") or theme.get("type", "?"),
                                   "type": theme.get("type"), "audio": found[0], "video": found[1]})
            if themes:
                out.append({"name": anime.get("name", "?"), "year": anime.get("year"), "score": score, "themes": themes})
        out.sort(key=lambda a: -a["score"])
        return out[:limit]

    @staticmethod
    def is_allowed_url(url: str) -> bool:
        """On ne télécharge que depuis animethemes.moe (empêche d'utiliser l'appli pour atteindre autre chose)."""
        from urllib.parse import urlparse
        u = urlparse(url or "")
        host = (u.hostname or "").lower()
        return u.scheme == "https" and (host == "animethemes.moe" or host.endswith(".animethemes.moe"))

    def _query_animes(self, title: str) -> List[Dict[str, Any]]:
        try:
            resp = self.session.get(
                f"{self.api_url}/anime",
                params={"q": title, "include": INCLUDES, "page[size]": 10},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("anime", [])
        except (requests.RequestException, ValueError) as e:
            logger.error("[AnimeThemes] Erreur API : %s", e)
            self.api_error = True          # panne passagère : ce n'est pas « introuvable »
            return []

    def _best_anime(self, title: str, animes: List[Dict[str, Any]]):
        """Compare le titre cherché au nom et aux titres alternatifs de chaque résultat."""
        best, best_score = None, 0
        for anime in animes:
            names = [anime.get("name", "")] + [s.get("text", "") for s in anime.get("animesynonyms", [])]
            score = max((similarity(title, n) for n in names if n), default=0)
            if score > best_score:
                best, best_score = anime, score
        if best_score < self.threshold:
            return None, best_score
        return best, best_score

    def _pick_theme(self, anime: Dict[str, Any]):
        """Choisit le générique selon l'ordre de préférence (OP1, puis ED1...)."""
        themes = anime.get("animethemes", [])
        for wanted in self.theme_types:
            candidates = [t for t in themes if t.get("type") == wanted]
            candidates.sort(key=lambda t: t.get("sequence") or 1)
            for theme in candidates:
                found = self._first_link(theme)
                if found:
                    return theme.get("slug", wanted), found[0], found[1]
        return None

    @staticmethod
    def _first_link(theme: Dict[str, Any]):
        for entry in theme.get("animethemeentries", []):
            for video in entry.get("videos", []):
                audio = (video.get("audio") or {}).get("link")
                link = video.get("link")
                if audio or link:
                    return audio, link
        return None

    # ------------------------------------------------------------------ téléchargement

    def download(self, url: str, output_path: Path) -> bool:
        """Télécharge le fichier (audio ou vidéo) puis le convertit en MP3 avec ffmpeg."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("[AnimeThemes] Téléchargement : %s", url)

        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "source"
            try:
                with self.session.get(url, stream=True, timeout=self.timeout) as resp:
                    resp.raise_for_status()
                    with open(raw, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=1 << 16):
                            f.write(chunk)
            except requests.RequestException as e:
                logger.error("[AnimeThemes] Téléchargement impossible : %s", e)
                return False

            tmp_out = Path(tmp) / "theme.mp3"
            if not convert_to_mp3(raw, tmp_out, self.target_db):
                return False

            safe_move(tmp_out, output_path)  # fonctionne aussi vers le NAS (autre disque, dates non modifiables)

        logger.info("[AnimeThemes] ✅ Enregistré : %s", output_path)
        return True

    def validate_config(self) -> bool:
        return super().validate_config() and bool(self.api_url)
