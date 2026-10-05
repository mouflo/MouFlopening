"""
Doublons de saisons : une saison qui a exactement le même thème que la série (ou qu'une autre saison de la même série).
Arrive quand AnimeThemes n'a pas de fiche propre à la saison et que la recherche retombe sur celle de la saison 1.
On compare les fichiers (taille puis empreinte) ; aucun fichier n'est modifié ici.
"""
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from . import library

logger = logging.getLogger(__name__)


def digest(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def theme_hashes(series: Path) -> Dict[str, str]:
    """{« série » ou numéro de saison : empreinte du thème} pour une série (seulement ce qui a un thème)."""
    out = {}
    t = library.find_theme(series)
    if t:
        out["série"] = digest(t)
    for n, folder in library.season_folders(series):
        t = library.find_theme(folder)
        if t:
            out[str(n)] = digest(t)
    return out


def find_duplicates(roots: List[str], skip_roots: Optional[set] = None) -> List[dict]:
    """[{"series", "id", "keep", "dups": [{"number", "id"}]}]. `skip_roots` : numéros de dossiers racine à ignorer (films)."""
    result = []
    for ri, root in enumerate(roots):
        if skip_roots and ri in skip_roots:
            continue
        for series in library.iter_series_folders([root]):
            seasons = library.season_folders(series)
            if not seasons:
                continue
            by_size: Dict[int, list] = {}
            entries = []
            t = library.find_theme(series)
            if t:
                entries.append(("série", t))
            for n, folder in seasons:
                t = library.find_theme(folder)
                if t:
                    entries.append((str(n), t))
            for label, t in entries:
                try:
                    by_size.setdefault(t.stat().st_size, []).append((label, t))
                except OSError:
                    pass
            groups: Dict[str, list] = {}
            for same in by_size.values():
                if len(same) > 1:                      # on ne calcule l'empreinte que s'il y a deux fichiers de même taille
                    for label, t in same:
                        try:
                            groups.setdefault(digest(t), []).append(label)
                        except OSError:
                            pass
            for labels in groups.values():
                if len(labels) < 2:
                    continue
                keep = "série" if "série" in labels else min((l for l in labels), key=lambda x: int(x))
                dups = [l for l in labels if l != keep]
                result.append({"series": library.clean_title(series.name), "keep": keep,
                               "dups": [{"number": int(l), "id": f"{ri}/{series.name}/{dict((str(n), f) for n, f in seasons)[l].name}"} for l in dups]})
    return result


# ------------------------------------------------ registre des sources (d'où vient chaque thème)
def load_sources(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def remember_source(path: Path, folder: Path, url: str) -> None:
    data = load_sources(path)
    data[str(folder)] = url
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.warning("Registre des sources illisible/inaccessible")


def sibling_themes(series: Path, folder: Path):
    """Thèmes déjà en place dans la série et ses autres saisons (hors `folder`) : [(dossier, fichier)]."""
    out = []
    for f in [series] + [p for _n, p in library.season_folders(series)]:
        if f != folder:
            t = library.find_theme(f)
            if t:
                out.append((f, t))
    return out
