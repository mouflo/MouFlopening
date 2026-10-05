"""
Parcours de la médiathèque : un dossier par série, le thème est enregistré dedans
sous le nom `theme.mp3` (convention reconnue automatiquement par Emby).
"""

import re
from pathlib import Path
from typing import Iterator, List, Tuple

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
