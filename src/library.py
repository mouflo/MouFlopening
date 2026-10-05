"""
Parcours de la médiathèque : un dossier par série, le thème est enregistré dedans
sous le nom `theme.mp3` (convention reconnue automatiquement par Emby).
"""

import re
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

THEME_FILENAME = "theme.mp3"
# Emby lit « theme.<extension audio> » ou tous les fichiers audio d'un sous-dossier « theme-music »
THEME_EXTS = (".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wav", ".opus", ".wma")
THEME_DIR = "theme-music"

# Dossiers système du Synology et dossiers de saison à ignorer
IGNORED_DIRS = {"@eaDir", "@tmp", "@__thumb", ".@__thumb", ".@tmp", ".hidden", ".trashes", "#recycle"}


def find_theme(folder: Path) -> Optional[Path]:
    """Le thème d'un dossier tel qu'Emby le voit (theme.mp3 d'abord), ou None."""
    for ext in THEME_EXTS:
        f = folder / f"theme{ext}"
        if f.is_file():
            return f
    d = folder / THEME_DIR
    try:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in THEME_EXTS:
                    return f
    except OSError:
        pass
    return None


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
            if find_theme(f) is None]


def missing_season_themes(roots: List[str]) -> List[Tuple[str, int, Path, Path]]:
    """Saisons sans theme.mp3 : liste de (titre de la série, numéro de saison, dossier de saison, dossier de série)."""
    out = []
    for series in iter_series_folders(roots):
        for number, folder in season_folders(series):
            if number >= 1 and find_theme(folder) is None:   # les « Specials » se choisissent à la main
                out.append((clean_title(series.name), number, folder, series))
    return out


# Dossiers de saison : « Season 1 », « Saison 02 », « S01 », « Specials » (= saison 0)
_SEASON_RE = re.compile(r"^(?:season|saison|s)[\s._-]*0*(\d{1,3})$", re.I)


def parse_season_folder(name: str) -> Optional[int]:
    """Numéro de saison d'après le nom du dossier, ou None si ce n'est pas un dossier de saison."""
    if name.strip().lower() in ("specials", "special", "spéciaux", "speciaux"):
        return 0
    m = _SEASON_RE.match(name.strip())
    return int(m.group(1)) if m else None


def season_folders(series: Path) -> List[Tuple[int, Path]]:
    """Dossiers de saison d'une série, triés par numéro."""
    out = []
    try:
        for sub in series.iterdir():
            if sub.is_dir() and sub.name not in IGNORED_DIRS and not sub.name.startswith("."):
                n = parse_season_folder(sub.name)
                if n is not None:
                    out.append((n, sub))
    except OSError:
        return []
    return sorted(out, key=lambda t: t[0])


def season_query(title: str, number: int) -> str:
    """Titre à chercher sur AnimeThemes pour une saison (la saison 1 se cherche sous le titre seul)."""
    return title if number <= 1 else f"{title} Season {number}"


def list_library(roots: List[str]) -> List[dict]:
    """Toutes les séries avec leur état. `id` = « numéro_du_dossier_racine/nom_du_dossier »."""
    items = []
    for i, root in enumerate(roots):
        base = Path(root)
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir(), key=lambda f: f.name.lower()):
            if folder.is_dir() and folder.name not in IGNORED_DIRS and not folder.name.startswith("."):
                seasons = [{"id": f"{i}/{folder.name}/{sub.name}", "name": sub.name, "number": n,
                            "has_theme": find_theme(sub) is not None} for n, sub in season_folders(folder)]
                items.append({"id": f"{i}/{folder.name}", "name": folder.name, "title": clean_title(folder.name),
                              "has_theme": find_theme(folder) is not None, "seasons": seasons})
    return items


def resolve_folder(roots: List[str], item_id: str) -> Optional[Path]:
    """Dossier d'une série (« 0/Serie ») ou d'une de ses saisons (« 0/Serie/Season 1 »), ou None si l'id est invalide."""
    return resolve_target(roots, item_id)[0]


def resolve_target(roots: List[str], item_id: str) -> Tuple[Optional[Path], Optional[Path], Optional[int]]:
    """(dossier visé, dossier de la série, numéro de saison ou None). Jamais en dehors de la médiathèque."""
    none = (None, None, None)
    try:
        parts = item_id.split("/")
        base = Path(roots[int(parts[0])])
    except (ValueError, IndexError, AttributeError):
        return none
    if len(parts) not in (2, 3):
        return none
    for name in parts[1:]:
        if not name or "\\" in name or name in (".", "..") or name in IGNORED_DIRS:
            return none
    series = base / parts[1]
    if not series.is_dir():
        return none
    if len(parts) == 2:
        return series, series, None
    number = parse_season_folder(parts[2])
    season = series / parts[2]
    if number is None or not season.is_dir():
        return none
    return season, series, number


# ---------------------------------------------------------------------------
# Catégories (onglets) : Anime, Séries, Films…
# ---------------------------------------------------------------------------
KINDS = ("anime", "series", "movie")
_KIND_WORDS = (("anime", ("manga", "anime", "animé", "anim", "cartoon", "dessin")),
               ("movie", ("film", "movie", "cinema", "cinéma")))


def guess_kind(name: str) -> str:
    """Type de médiathèque d'après le nom du dossier : Manga/Anime -> anime, Films -> movie, sinon séries."""
    low = name.lower()
    for kind, words in _KIND_WORDS:
        if any(w in low for w in words):
            return kind
    return "series"


def discover_categories(cfg: dict) -> List[dict]:
    """
    Liste des onglets : [{"name", "path", "kind", "ok"}].
    Sources : `library.categories` (nom, chemin, type) puis chaque sous-dossier de `library.auto_parent`
    (le type est deviné d'après le nom), puis l'ancien réglage `library.paths`.
    """
    lib = (cfg or {}).get("library", {})
    cats, seen = [], set()

    def add(name, path, kind=None):
        key = str(Path(path).resolve()) if path else ""
        if not path or key in seen:
            return
        seen.add(key)
        k = kind if kind in KINDS else guess_kind(name)
        cats.append({"name": name, "path": str(path), "kind": k, "ok": Path(path).is_dir()})

    for c in lib.get("categories", []) or []:
        if isinstance(c, dict) and c.get("path"):
            add(c.get("name") or Path(c["path"]).name, c["path"], c.get("kind"))
    parent = lib.get("auto_parent")
    if parent and Path(parent).is_dir():
        for sub in sorted(Path(parent).iterdir(), key=lambda f: f.name.lower()):
            if sub.is_dir() and sub.name not in IGNORED_DIRS and not sub.name.startswith((".", "@", "#")):
                add(sub.name, str(sub))
    for path in lib.get("paths", []) or []:
        add(Path(path).name, path)
    cats.sort(key=lambda c: KINDS.index(c["kind"]))   # anime, séries, films (tri stable)
    return cats
