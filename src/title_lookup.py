"""
Titre original d'un film / d'une série retrouvé sur Internet (TheMovieDB).

Sert quand Emby ne connaît pas le titre : par exemple un dossier créé par Radarr pour un film pas encore
téléchargé (dossier vide, donc jamais scanné par Emby). On cherche avec le titre du dossier et l'année.
"""

import logging
import re
from typing import Tuple

import requests

from .matching import similarity

logger = logging.getLogger(__name__)
_YEAR_RE = re.compile(r"\(\s*((?:19|20)\d{2})\s*\)")
_TMDB = "https://api.themoviedb.org/3"


def _is_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(ord(c) < 0x250 for c in letters)


def _get(path: str, key: str, params: dict):
    headers = {}
    params = dict(params)
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    else:
        params["api_key"] = key
    from .netfix import repair_urllib3
    repair_urllib3()
    return requests.get(_TMDB + path, params=params, headers=headers, timeout=8)


def _best(folder_name: str, clean: str, kind: str, key: str):
    """(meilleur résultat TMDB ou None, remarque)."""
    if not key or "TON_CLE" in key:
        return None, "clé TheMovieDB non configurée (bouton « Clé TMDB »)"
    year_match = _YEAR_RE.search(folder_name)
    year = year_match.group(1) if year_match else ""
    movie = kind == "movie"
    params = {"query": clean, "language": "en-US", "include_adult": "false"}
    if year:
        params["year" if movie else "first_air_date_year"] = year
    try:
        r = _get("/search/movie" if movie else "/search/tv", key, params)
        if r.status_code in (401, 403):
            return None, "TheMovieDB refuse la clé"
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results and year:                       # année du dossier parfois décalée : on réessaie sans
            params.pop("year", None); params.pop("first_air_date_year", None)
            r = _get("/search/movie" if movie else "/search/tv", key, params)
            r.raise_for_status()
            results = r.json().get("results", [])
    except requests.exceptions.RequestException as e:
        logger.warning("[TMDB] Recherche impossible : %s", e)
        return None, f"TheMovieDB injoignable ({type(e).__name__})"
    if not results:
        return None, "film introuvable sur TheMovieDB" if movie else "série introuvable sur TheMovieDB"

    def label(x):
        return x.get("title") if movie else x.get("name")
    # le résultat dont un des titres ressemble le plus à celui du dossier (le premier en cas d'égalité)
    best = max(results[:5], key=lambda x: max(similarity(clean, label(x) or ""), similarity(clean, x.get("original_title") or x.get("original_name") or "")))
    return best, ""


def tmdb_id(folder_name: str, clean: str, kind: str, key: str) -> Tuple[int, str]:
    """(identifiant TheMovieDB, remarque) ; 0 si introuvable."""
    best, why = _best(folder_name, clean, kind, key)
    if best and best.get("id"):
        logger.info("[TMDB] « %s » → identifiant %s (%s)", clean, best["id"], best.get("title") or best.get("name"))
        return int(best["id"]), ""
    logger.info("[TMDB] « %s » : %s", clean, why)
    return 0, why


def original_title(folder_name: str, clean: str, kind: str, key: str) -> Tuple[str, str]:
    """(titre, remarque). Titre « » si rien de fiable ; la remarque dit pourquoi."""
    best, why = _best(folder_name, clean, kind, key)
    if not best:
        return "", why
    movie = kind == "movie"
    original = (best.get("original_title") if movie else best.get("original_name")) or ""
    english = (best.get("title") if movie else best.get("name")) or ""
    # anime : l'original est en japonais, les sources connaissent le titre anglais / romaji
    pick = original if (movie and _is_latin(original)) else english
    logger.info("[TMDB] « %s » → « %s » (original « %s », anglais « %s »)", clean, pick, original, english)
    return pick.strip(), ""
