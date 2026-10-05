"""
Parcours de la médiathèque : un dossier par série, le thème est enregistré dedans
sous le nom `theme.mp3` (convention reconnue automatiquement par Emby).
"""

import re
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

THEME_FILENAME = "theme.mp3"

# Dossiers système du Synology et dossiers de saison à ignorer
IGNORED_DIRS = {"@eaDir", "@tmp", "@__thumb", ".@__thumb", ".@tmp", ".hidden", ".trashes", "#recycle"}


def clean_title(folder_name: str) -> str:
    """« Fairy Tail (2009) [tvdbid-1234] » -> « Fairy Tail »"""
    name = re.sub(r"\[[^\]]*\]|\{[^}]*\}", "", folder_name)   # [tags] et {tags}
    name = re.sub(r"\(\s*(19|20)\d{2}\s*\)", "", name)         # (année)
    return re.sub(r"\s+", " ", name).strip(" -._")


def iter_series_folders(roots: List[str]) -> Iterator[Path]:
    """Liste les dossiers de séries (niveau 1 sous chaque dossier racine)."""
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            if folder.is_dir() and folder.name not in IGNORED_DIRS and not folder.name.startswith("."):
                yield folder


def missing_themes(roots: List[str]) -> List[Tuple[str, Path]]:
    """Séries sans theme.mp3 : liste de (titre nettoyé, dossier)."""
    return [(clean_title(f.name), f) for f in iter_series_folders(roots)
            if not (f / THEME_FILENAME).exists()]


def list_library(roots: List[str]) -> List[dict]:
    """Toutes les séries avec leur état. `id` = « numéro_du_dossier_racine/nom_du_dossier »."""
    items = []
    for i, root in enumerate(roots):
        base = Path(root)
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir(), key=lambda f: f.name.lower()):
            if folder.is_dir() and folder.name not in IGNORED_DIRS and not folder.name.startswith("."):
                items.append({"id": f"{i}/{folder.name}", "name": folder.name, "title": clean_title(folder.name),
                              "has_theme": (folder / THEME_FILENAME).exists()})
    return items


def resolve_folder(roots: List[str], item_id: str) -> Optional[Path]:
    """Retrouve le dossier d'une série à partir de son id, ou None si l'id est invalide (jamais hors médiathèque)."""
    try:
        idx, name = item_id.split("/", 1)
        base = Path(roots[int(idx)])
    except (ValueError, IndexError, AttributeError):
        return None
    if not name or "/" in name or "\\" in name or name in (".", "..") or name in IGNORED_DIRS:
        return None
    folder = base / name
    return folder if folder.is_dir() else None
