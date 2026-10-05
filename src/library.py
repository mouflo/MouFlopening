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


MIN_THEME_BYTES = 8 * 1024     # en dessous, le fichier est vide ou tronqué (reste d'un plugin ou d'un téléchargement cassé)


def _usable(f: Path) -> bool:
    """Un vrai fichier audio, pas un theme.mp3 vide ou corrompu : il compte alors comme « sans thème » et sera remplacé."""
    try:
        return f.is_file() and f.stat().st_size >= MIN_THEME_BYTES
    except OSError:
        return False


def find_theme(folder: Path) -> Optional[Path]:
    """Le thème d'un dossier tel qu'Emby le voit (theme.mp3 d'abord), ou None (fichier absent, vide ou tronqué)."""
    for ext in THEME_EXTS:
        f = folder / f"theme{ext}"
        if _usable(f):
            return f
    d = folder / THEME_DIR
    try:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if _usable(f) and f.suffix.lower() in THEME_EXTS:
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
# Onglets : Animes, Séries, Films (les dossiers du même type sont regroupés, ex. Films HD + Films 4K)
# ---------------------------------------------------------------------------
KINDS = ("anime", "series", "movie")
DEFAULT_NAMES = {"anime": "Animes", "series": "Séries", "movie": "Films"}
_KIND_RE = (("anime", re.compile(r"manga|anime|animé|cartoon|dessin", re.I)),
            ("movie", re.compile(r"film|movie|cinema|cinéma|(?<![a-z0-9])(4k|uhd|hd)(?![a-z0-9])", re.I)),
            ("series", re.compile(r"s[ée]rie|(?<![a-z0-9])(tv|show|shows)(?![a-z0-9])", re.I)))


def guess_kind(name: str) -> Optional[str]:
    """Type d'après le nom du dossier : Manga/Anime -> anime, Films/HD/4K -> movie, Séries/TV -> series, sinon None (ignoré)."""
    for kind, rx in _KIND_RE:
        if rx.search(name):
            return kind
    return None


def discover_categories(cfg: dict, ignored: Optional[list] = None) -> List[dict]:
    """
    Les onglets : [{"name", "kind", "paths": [...], "ok"}], dans l'ordre Animes, Séries, Films.
    Sources : `library.categories` (chemin ou chemins + type), puis chaque sous-dossier de `library.auto_parent`
    dont le nom évoque un type connu (les autres sont ignorés et ajoutés à `ignored`), puis l'ancien `library.paths`.
    """
    lib = (cfg or {}).get("library", {})
    groups = {k: {"name": None, "paths": []} for k in KINDS}
    seen = set()

    def add(kind, path, name=None):
        if kind not in KINDS or not path:
            return
        key = str(Path(path).resolve())
        if key in seen:
            return
        seen.add(key)
        groups[kind]["paths"].append(str(path))
        groups[kind]["name"] = groups[kind]["name"] or name

    for c in lib.get("categories", []) or []:
        if not isinstance(c, dict):
            continue
        for path in ([c["path"]] if c.get("path") else []) + list(c.get("paths") or []):
            add(c.get("kind") or guess_kind(c.get("name") or Path(path).name), path, c.get("name"))
    parent = lib.get("auto_parent")
    if parent and Path(parent).is_dir():
        for sub in sorted(Path(parent).iterdir(), key=lambda f: f.name.lower()):
            if sub.is_dir() and sub.name not in IGNORED_DIRS and not sub.name.startswith((".", "@", "#")):
                kind = guess_kind(sub.name)
                if kind:
                    add(kind, str(sub))
                elif ignored is not None:
                    ignored.append(sub.name)
    for path in lib.get("paths", []) or []:
        add(guess_kind(Path(path).name) or "series", path)
    return [{"name": g["name"] or DEFAULT_NAMES[k], "kind": k, "paths": g["paths"],
             "ok": all(Path(p).is_dir() for p in g["paths"])} for k, g in groups.items() if g["paths"]]
