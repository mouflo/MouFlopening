"""Index de la médiathèque (SQLite) : la liste des titres, de leurs saisons et de la présence d'un thème, gardée entre deux ouvertures.

Avant, chaque ouverture de la page parcourait tout le NAS (≈ 1 700 titres et 1 700 saisons : un dossier ouvert et plusieurs fichiers cherchés
pour chacun) : 5 à 6 secondes à froid. Maintenant chaque titre est mémorisé avec la date de son dossier (et celle de chacune de ses saisons) :
un titre dont les dates n'ont pas bougé n'est pas relu. Un thème qui arrive, un dossier renommé ou effacé change la date du dossier : le titre
concerné est recalculé tout seul. Le résultat est identique à library.list_library (même format, même ordre).

Le fichier est data/index.sqlite (jamais sur GitHub) ; s'il est abîmé ou absent, tout est recalculé une fois, sans rien perdre.
"""
import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional

from src import library
from src.library import IGNORED_DIRS, clean_title, find_theme, season_folders, _vide

logger = logging.getLogger("mouflopening")
_VERROU = threading.Lock()                  # une seule mise à jour à la fois
_BASE = {"chemin": None, "dernier_complet": 0.0}
VERSION = 1                                 # change quand le contenu mémorisé change : tout est recalculé une fois


def configurer(chemin) -> None:
    """Où se trouve le fichier SQLite (None : pas d'index, library.list_library comme avant)."""
    _BASE["chemin"] = Path(chemin) if chemin else None


def _connexion() -> sqlite3.Connection:
    c = sqlite3.connect(str(_BASE["chemin"]), timeout=30)
    c.execute("CREATE TABLE IF NOT EXISTS titres (chemin TEXT PRIMARY KEY, mtime INTEGER NOT NULL, donnees TEXT NOT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT)")
    v = c.execute("SELECT valeur FROM meta WHERE cle='version'").fetchone()
    if not v or v[0] != str(VERSION):
        c.execute("DELETE FROM titres")
        c.execute("INSERT OR REPLACE INTO meta VALUES ('version', ?)", (str(VERSION),))
        c.commit()
    return c


def _calculer(dossier: Path, mtime: int) -> dict:
    """Ce que la liste affiche d'un titre : le même calcul que library.list_library, avec la date de chaque saison pour la vérification."""
    if _vide(dossier):
        return {"vide": True}
    saisons = []
    for n, sub in season_folders(dossier):
        try:
            m = sub.stat().st_mtime_ns
        except OSError:
            m = 0
        saisons.append({"name": sub.name, "number": n, "has_theme": find_theme(sub) is not None, "mtime": m})
    return {"vide": False, "titre": clean_title(dossier.name), "has_theme": find_theme(dossier) is not None, "seasons": saisons}


def _saisons_a_jour(dossier: str, d: dict) -> bool:
    """Une saison dont le dossier a changé (un thème posé, par exemple) ne change pas la date du dossier du titre : on la regarde aussi."""
    for s in d.get("seasons", []):
        try:
            if os.stat(os.path.join(dossier, s["name"])).st_mtime_ns != s["mtime"]:
                return False
        except OSError:
            return False
    return True


def lister(roots: List[str], tout: bool = False) -> List[dict]:
    """Même résultat que library.list_library(roots). `tout` : recalcule tous les titres (contrôle complet, fait en fond de temps en temps).
    Sans index configuré ou si SQLite se plaint, on retombe sur library.list_library."""
    if not _BASE["chemin"]:
        return library.list_library(roots)
    try:
        return _lister(roots, tout)
    except sqlite3.Error as e:
        logger.warning("Index de la médiathèque inutilisable (%s) : liste relue sans lui", e)
        return library.list_library(roots)


def _lister(roots: List[str], tout: bool) -> List[dict]:
    with _VERROU:
        con = _connexion()
        try:
            cache = {c: (m, json.loads(d)) for c, m, d in con.execute("SELECT chemin, mtime, donnees FROM titres")}
            items, vus, racines_lues, maj = [], set(), [], []
            for i, root in enumerate(roots):
                base = Path(root)
                if not base.is_dir():
                    continue
                racines_lues.append(str(base))
                try:
                    entrees = sorted(os.scandir(base), key=lambda e: e.name.lower())
                except OSError:
                    continue
                for e in entrees:
                    try:
                        if not e.is_dir() or e.name in IGNORED_DIRS or e.name.startswith("."):
                            continue
                        mtime = e.stat().st_mtime_ns
                    except OSError:
                        continue
                    vus.add(e.path)
                    c = cache.get(e.path)
                    d = c[1] if c and not tout and c[0] == mtime and _saisons_a_jour(e.path, c[1]) else None
                    if d is None:
                        d = _calculer(Path(e.path), mtime)
                        maj.append((e.path, mtime, json.dumps(d, ensure_ascii=False)))
                    if d["vide"]:
                        continue
                    items.append({"id": f"{i}/{e.name}", "name": e.name, "title": d["titre"], "has_theme": d["has_theme"],
                                  "seasons": [{"id": f"{i}/{e.name}/{s['name']}", "name": s["name"], "number": s["number"], "has_theme": s["has_theme"]}
                                              for s in d["seasons"]]})
            # un titre effacé du NAS disparaît de l'index, mais seulement pour les dossiers racine lus (un partage absent ne vide rien)
            oublies = [c for c in cache if c not in vus and any(c.startswith(r + os.sep) for r in racines_lues)]
            if maj or oublies:
                con.executemany("INSERT OR REPLACE INTO titres VALUES (?, ?, ?)", maj)
                con.executemany("DELETE FROM titres WHERE chemin = ?", [(c,) for c in oublies])
                con.commit()
            if tout:
                _BASE["dernier_complet"] = time.time()
            return items
        finally:
            con.close()


def boucle(roots_fn, intervalle: int = 900) -> None:
    """En arrière-plan : un contrôle complet (tous les titres recalculés) toutes les 15 minutes, au cas où une date de dossier n'aurait pas
    bougé comme prévu (changement fait par un autre ordinateur du réseau, par exemple). Ne gêne personne : la liste servie reste celle de l'index."""
    time.sleep(120)
    while True:
        try:
            t = time.time()
            n = len(lister(roots_fn(), tout=True))
            logger.info("Index de la médiathèque : contrôle complet de %d titres en %.1f s", n, time.time() - t)
        except Exception as e:
            logger.warning("Contrôle complet de l'index : %s", e)
        time.sleep(intervalle)
