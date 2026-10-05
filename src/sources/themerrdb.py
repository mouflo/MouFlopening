"""
ThemerrDB (https://github.com/LizardByte/ThemerrDB) : base communautaire qui associe un film ou une série
(par identifiant TheMovieDB) à une vidéo YouTube de son thème, relue et validée par des humains.

On n'y trouve que des liens YouTube : le téléchargement et la conversion restent ceux de la source YouTube.
Licence de la base : BSD-3-Clause.
"""

import logging
import re
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)
_BASE = "https://app.lizardbyte.dev/ThemerrDB"
_ID_RE = re.compile(r"(?:youtu\.be/|[?&]v=|/embed/)([\w-]{11})")


def lookup(kind: str, tmdb_id: int, timeout: float = 8) -> Tuple[Optional[dict], str]:
    """(thème, remarque). thème = {"title", "video_id"} ou None si la base n'a rien pour ce titre."""
    if not tmdb_id:
        return None, ""
    path = "movies" if kind == "movie" else "tv_shows"
    try:
        r = requests.get(f"{_BASE}/{path}/themoviedb/{int(tmdb_id)}.json", timeout=timeout)
    except requests.exceptions.RequestException as e:
        logger.info("[ThemerrDB] injoignable : %s", e)
        return None, "ThemerrDB injoignable"
    if r.status_code == 404:
        return None, "pas de thème dans ThemerrDB pour ce titre"
    if r.status_code >= 400:
        return None, f"ThemerrDB a répondu {r.status_code}"
    try:
        data = r.json()
    except ValueError:
        return None, "réponse ThemerrDB illisible"
    url = str(data.get("youtube_theme_url") or "")
    m = _ID_RE.search(url)
    if not m:
        return None, "pas de thème dans ThemerrDB pour ce titre"
    title = str(data.get("title") or data.get("name") or "").strip()
    logger.info("[ThemerrDB] %s %s → %s", path, tmdb_id, m.group(1))
    return {"title": title, "video_id": m.group(1)}, ""
