#!/usr/bin/env python3
"""
MouFlopening - interface web (même conception que MouFloster et MouFlanimeXer).

- Liste de la médiathèque : séries avec ou sans thème
- Choix manuel : on écoute les génériques proposés par AnimeThemes puis on clique « Utiliser »
- Mode automatique : une série, ou toutes celles qui n'ont pas de thème (avec barre de progression)
- Le thème est enregistré sous theme.mp3 dans le dossier de la série, puis Emby actualise cette série seule
"""

import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from src.config import load_config, load_secrets_env

BASE_DIR = Path(__file__).resolve().parent
load_secrets_env()   # identifiants et clé Emby (data/secrets.env), avant l'initialisation de la connexion


def _tmdb_key_from_moufloster():
    """Pas de clé TheMovieDB ici : on reprend celle de MouFloster (même serveur, même compte) sans la copier ni l'afficher."""
    if os.getenv("TMDB_API_KEY", "").strip():
        return
    try:
        for line in Path("/opt/moufloster/data/secrets.env").read_text(encoding="utf-8").splitlines():
            if line.startswith("TMDB_API_KEY="):
                os.environ["TMDB_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                return
    except OSError:
        pass


_tmdb_key_from_moufloster()

from src import library
from src.emby_client import EmbyClient
from src.fsutil import safe_copy, safe_move
from src.library import THEME_DIR, THEME_EXTS, THEME_FILENAME, find_theme
from src.sources.animethemes import AnimeThemesSource
from src.sources.youtube import YouTubeSource
from src.sources.base_source import ThemeResult

BASE_VERSION = "0.2"


def _changelog_version():
    """Numéro de version = la dernière entrée du CHANGELOG.md (celle que je décris à chaque mise à jour)."""
    try:
        m = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (BASE_DIR / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def get_version():
    num = _changelog_version()
    try:
        short = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        if num:
            return f"v{num} ({short})"
        count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        return f"v{BASE_VERSION}.{count} ({short})"
    except Exception:
        return f"v{num or BASE_VERSION}"


APP_VERSION = get_version()
CONFIG = load_config()
IGNORED_FOLDERS = []
CATS = library.discover_categories(CONFIG, IGNORED_FOLDERS)   # onglets : Animes, Séries, Films (dossiers du même type regroupés)
ROOTS, ROOT_CAT = [], []                                      # dossiers racine à plat, et l'onglet de chacun
for _i, _c in enumerate(CATS):
    for _p in _c["paths"]:
        ROOTS.append(_p)
        ROOT_CAT.append(_i)
EMBY = EmbyClient(CONFIG.get("emby", {}))
TARGET_DB = float(CONFIG.get("audio", {}).get("target_db", 89))   # niveau de chaque thème (référence ReplayGain / MP3Gain)
SOURCE = AnimeThemesSource(CONFIG.get("sources", {}).get("animethemes", {"enabled": True}),
                           threshold=CONFIG.get("matching", {}).get("threshold", 70), target_db=TARGET_DB)

YOUTUBE = YouTubeSource(CONFIG.get("sources", {}).get("youtube", {}), target_db=TARGET_DB)


def source_for(kind):
    """AnimeThemes pour les animes, YouTube pour les séries et les films."""
    return SOURCE if kind == "anime" else YOUTUBE


def kind_of(item_id):
    """Type (anime / series / movie) de l'onglet auquel appartient un identifiant « n/Dossier »."""
    try:
        return CATS[ROOT_CAT[int(str(item_id).split("/")[0])]]["kind"]
    except (ValueError, IndexError):
        return "anime"


app = Flask(__name__)

from src import progress
from src import skipped
from src.netfix import repair_urllib3


@app.before_request
def _repair_http():
    repair_urllib3()          # yt-dlp abîme urllib3 : on le répare avant chaque requête (voir src/netfix.py)

import auth
import diag

diag.setup_logging()
logger = logging.getLogger("mouflopening")
auth.init_app(app, APP_VERSION)

_work_lock = threading.Lock()   # un seul téléchargement/conversion à la fois (ménage le NAS et le CPU)

# Anciens thèmes mis de côté : sur le NAS (dossier MouFlopening), repli sur data/ si le partage n'est pas accessible
OLD_BACKUP_DIR = BASE_DIR / "data" / "themes-backup"
_BACKUP_CFG = Path(CONFIG.get("themes", {}).get("backup_dir") or "/mnt/mouflosyno/MouFlopening/Anciens thèmes")


def _backup_dir():
    try:
        _BACKUP_CFG.mkdir(parents=True, exist_ok=True)
        if os.access(_BACKUP_CFG, os.W_OK):
            return _BACKUP_CFG
    except OSError:
        pass
    logger.warning("Dossier de sauvegarde %s inaccessible (partage monté ?) : repli sur %s", _BACKUP_CFG, OLD_BACKUP_DIR)
    return OLD_BACKUP_DIR


def _migrate_old_backups():
    """Une fois : les sauvegardes déjà faites dans data/themes-backup sont déplacées vers le NAS."""
    if not OLD_BACKUP_DIR.is_dir() or not any(OLD_BACKUP_DIR.iterdir()):
        return
    dest = _backup_dir()
    if dest == OLD_BACKUP_DIR:
        return
    for item in list(OLD_BACKUP_DIR.iterdir()):
        try:
            target = dest / item.name
            if not target.exists():
                safe_move(item, target)
                logger.info("Sauvegarde déplacée vers le NAS : %s", target)
        except OSError as e:
            logger.warning("Déplacement impossible (%s) : %s", item.name, e)
NORMALIZED_FILE = BASE_DIR / "data" / "normalized.json"
skipped.init(BASE_DIR / "data" / "skipped.json")


def _slug(text):
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:80] or "theme"


def _backup_name(folder, ext, extra=""):
    """Nom libre dans le dossier des anciens thèmes (jamais d'écrasement, même deux fois dans la même seconde)."""
    dest = _backup_dir()
    base = f"{datetime.now():%Y%m%d-%H%M%S}_{_slug(folder.parent.name)}_{_slug(folder.name)}{('_' + _slug(extra)) if extra else ''}"
    target, n = dest / f"{base}{ext}", 2
    while target.exists():
        target, n = dest / f"{base}_{n}{ext}", n + 1
    return target


def _backup_existing(folder, keep=None):
    """L'ancien thème (theme.mp3, theme.flac…, ou fichiers du dossier theme-music) est mis de côté, jamais supprimé.
    keep : fichier à laisser en place (le nouveau thème)."""
    olds = [folder / f"theme{ext}" for ext in THEME_EXTS]
    d = folder / library.THEME_DIR
    try:
        if d.is_dir():
            olds += [f for f in sorted(d.iterdir()) if f.suffix.lower() in THEME_EXTS]
    except OSError:
        pass
    for old in olds:
        if keep is not None and old == keep or not old.is_file():
            continue
        target = _backup_name(folder, old.suffix.lower(), old.stem if old.parent != folder else "")
        safe_move(old, target)
        logger.info("Ancien thème mis de côté : %s", target)


def _install_theme(tmp, folder):
    """Pose le nouveau thème (tmp, déjà dans le dossier) sans jamais laisser le titre sans thème :
    l'ancien theme.mp3 est d'abord COPIÉ dans les anciens thèmes, puis remplacé d'un coup ; les autres formats sont ensuite mis de côté."""
    cur = folder / THEME_FILENAME
    if cur.is_file():
        target = _backup_name(folder, ".mp3")
        safe_copy(cur, target)                    # en cas d'échec : exception, rien n'a bougé
        logger.info("Ancien thème mis de côté : %s", target)
    safe_move(tmp, cur)                           # même dossier : remplacement en une fois (os.replace)
    _backup_existing(folder, keep=cur)


SOURCES_FILE = BASE_DIR / "data" / "theme_sources.json"
TRANSIENT = "⏳ "      # début des messages d'échec passager (réseau, écriture) : le titre n'est pas « mis de côté »


def _write_problem(folder, err):
    """Explique simplement pourquoi on ne peut pas écrire dans un dossier du NAS."""
    stuck = [p.name for p in folder.glob("*.partiel*")] if folder.is_dir() else []
    if stuck:
        return (f"un fichier temporaire bloqué ({', '.join(stuck[:3])}) empêche l'écriture dans « {folder.name} » : "
                "supprime-le depuis le NAS (ou vérifie ses droits), puis réessaie")
    if not os.access(folder, os.W_OK):
        return f"le dossier « {folder.name} » est en lecture seule pour l'appli (droits du dossier sur le NAS)"
    return f"écriture impossible dans « {folder.name} » ({getattr(err, 'strerror', None) or err}) : vérifie les droits du dossier sur le NAS"


def _clear_partials(folder):
    """Restes d'un essai précédent (theme.nouveau.partiel, …partiel.partiel) : retirés avant d'écrire."""
    for p in folder.glob("theme*.partiel"):          # couvre aussi « …partiel.partiel »
        try:
            p.unlink()
        except OSError as e:
            logger.warning("Fichier temporaire impossible à supprimer : %s (%s)", p, e)


def _download_replace(source, url, folder, trusted=False, forbid_same_as=None, any_url=False):
    """Télécharge d'abord à côté ; l'ancien thème n'est mis de côté qu'une fois le nouveau bien reçu. -> (succès, raison)
    forbid_same_as : (dossier de la série) : refuse un thème identique à celui de la série ou d'une autre saison."""
    tmp = folder / "theme.nouveau.partiel"
    progress.say("Téléchargement du thème…")
    _clear_partials(folder)
    try:
        if any_url:
            done = source.download(url, tmp, trusted=True, any_url=True)
        else:
            done = source.download(url, tmp, trusted=True) if trusted and hasattr(source, "_probe_duration") else source.download(url, tmp)
    except OSError as e:                       # le son est prêt mais le dossier du NAS refuse l'écriture
        logger.error("Écriture impossible dans %s : %s", folder, e)
        return False, TRANSIENT + _write_problem(folder, e)
    if not done:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False, getattr(source, "last_error", "") or "téléchargement ou conversion impossible (détails : bouton Journal)"
    if forbid_same_as is not None:
        from src import dupes
        try:
            mine = dupes.digest(tmp)
            for other, theme in dupes.sibling_themes(forbid_same_as, folder):
                if dupes.digest(theme) == mine:
                    tmp.unlink()
                    return False, "même thème que " + ("la série" if other == forbid_same_as else other.name) + " (AnimeThemes n'a pas de fiche propre à cette saison) : à choisir à la main"
        except OSError:
            pass
    progress.say("Mise en place du thème (l'ancien est mis de côté)…")
    try:
        _maybe_trim(tmp)
        _install_theme(tmp, folder)
    except OSError as e:
        logger.error("Mise en place impossible dans %s : %s", folder, e)
        try:
            tmp.unlink()
        except OSError:
            pass
        return False, TRANSIENT + _write_problem(folder, e) + " (l'ancien thème est conservé)"
    from src import dupes
    dupes.remember_source(SOURCES_FILE, folder, url)
    return True, ""


def _read_registry():
    try:
        return json.loads(NORMALIZED_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _signature(path):
    st = path.stat()
    return [st.st_size, int(st.st_mtime)]


# ---------------------------------------------------------------------------
# Téléchargement automatique de toutes les séries sans thème (en arrière-plan)
# ---------------------------------------------------------------------------

BATCH = {"kind": "download", "running": False, "stop": False, "total": 0, "done": 0, "failed": 0, "current": "", "messages": []}
_batch_lock = threading.Lock()


def _batch_note(text):
    logger.info("[lot] %s", text)
    with _batch_lock:
        BATCH["messages"] = (BATCH["messages"] + [text])[-200:]


def _batch_state_text():
    with _batch_lock:
        b = dict(BATCH)
    if not b["running"] and not b["total"]:
        return "aucun lot lancé depuis le démarrage"
    norm = b.get("kind") == "normalize"
    return (f"{'Normalisation' if norm else 'Téléchargement'} · {'EN COURS' if b['running'] else 'terminé'} · {b['done'] + b['failed']}/{b['total']} "
            f"({'vérifiés' if norm else 'ajoutés'} {b['done']}, {'erreurs' if norm else 'introuvables'} {b['failed']}) · en cours : {b['current'] or '-'}")


def _run_batch(limit, with_seasons, cat=0, fresh=True):
    """fresh : nouveau lot (journal remis à zéro) ; False pour les onglets suivants du lot de nuit."""
    kind = CATS[cat]["kind"]
    added_titles, n_failed = [], 0
    try:
        return _run_batch_inner(limit, with_seasons, cat, kind, fresh, added_titles)
    except Exception:
        logger.exception("Le lot s'est arrêté sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
        return {"kind": kind, "added": added_titles, "failed": BATCH.get("failed", 0)}
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def _nas_problem(roots):
    """Dossiers de médiathèque absents ou non modifiables (partage réseau non monté…) -> texte, ou '' si tout va bien."""
    bad = [str(r) for r in roots if not (os.path.isdir(r) and os.access(r, os.W_OK))]
    return ", ".join(bad)


def _run_batch_inner(limit, with_seasons, cat, kind, fresh, added_titles):
    roots = list(CATS[cat]["paths"])
    bad = _nas_problem(roots)
    if bad:                                     # NAS non monté : on s'arrête tout de suite, aucun titre n'est mis de côté
        with _batch_lock:
            BATCH.update(kind="download", running=True, total=0, done=0, failed=0, current="")
            if fresh:
                BATCH["messages"] = []
        _batch_note(f"⚠️ Partage réseau inaccessible : {bad} — lot arrêté, rien n'a été touché")
        return {"kind": kind, "added": [], "failed": 0, "failures": [], "nas_error": bad}
    todo = [("film" if kind == "movie" else "série", title, folder, folder, None) for title, folder in library.missing_themes(roots)]
    if with_seasons and kind == "anime":          # films et séries : seul ThemerrDB est accepté, et il ne connaît pas les saisons
        # La saison 1 n'est jamais cherchée automatiquement : elle aurait le même générique que la série (doublon dans Emby,
        # même si le thème de la série a été choisi à la main et ne vient pas de la même source). À choisir à la main.
        todo += [(f"saison {n}", title, folder, series, n) for title, n, folder, series in library.missing_season_themes(roots) if n >= 2]
    sk = skipped.all_keys(nightly.settings().get("retry_days", 30))     # au-delà de N jours, les titres mis de côté sont retentés
    n_all = len(todo)
    todo = [t for t in todo if str(t[2]) not in sk]          # les titres déjà recherchés sans résultat sont laissés de côté
    n_skip = n_all - len(todo)
    if limit:
        todo = todo[:limit]
    with _batch_lock:
        BATCH.update(kind="download", running=True, total=len(todo), done=0, failed=0, current="")
        if fresh:
            BATCH["messages"] = []
    n_failed, failures = 0, []
    _batch_note(("" if fresh else f"— {CATS[cat]['name']} — ") + f"{len(todo)} thème(s) à chercher" + (" (séries et saisons)" if with_seasons else " (séries)")
                + (f" · {n_skip} mis de côté (déjà cherchés sans résultat) ignoré(s)" if n_skip else ""))
    if True:
        for _what, title, folder, series, number in todo:
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            label = title if number is None else f"{title} — saison {number}"
            with _batch_lock:
                BATCH["current"] = label
            ok, msg = _auto_one(folder, title, series, number, kind=kind)   # kind = type de l'onglet (anime / série / film)
            if ok:
                skipped.remove(folder)
            elif kind == "anime" and not msg.startswith(TRANSIENT):   # panne passagère : pas mis de côté. Films et séries : « pas dans ThemerrDB » ne veut pas dire « introuvable » (recherche à la main possible)
                skipped.add(folder, msg)
            with _batch_lock:
                BATCH["done" if ok else "failed"] += 1
            if ok:
                added_titles.append(label)
            else:
                n_failed += 1
                failures.append((label, msg))
            _batch_note(("✅ " if ok else "❌ ") + f"{label} — {msg}")
    return {"kind": kind, "added": added_titles, "failed": n_failed, "failures": failures}


def year_of(name):
    """Année d'un dossier « Titre (2025) » (None si absente)."""
    m = re.search(r"\(\s*((?:19|20)\d{2})\s*\)", name or "")
    return int(m.group(1)) if m else None


def original_title_for(series, title, kind):
    """Titre original : d'abord Emby, sinon TheMovieDB (dossier vide créé par Radarr, pas encore scanné…). -> (titre, remarque)"""
    orig, why = EMBY.original_title(series.name, title, kind, series.parent.name)
    if orig:
        return orig, ""
    from src import title_lookup
    online, why2 = title_lookup.original_title(series.name, library.clean_title(series.name), kind, os.getenv("TMDB_API_KEY", "").strip())
    if online:
        return online, ""
    return "", f"{why} ; {why2}"


def themerr_for(series, kind):
    """Thème choisi par la base ThemerrDB (films et séries, via l'identifiant TheMovieDB).
    L'identifiant est cherché d'abord avec la correspondance la plus sûre : celui qu'Emby connaît déjà ; sinon d'après le TITRE ORIGINAL
    (la plupart des films sont américains, la base les connaît sous ce titre), puis d'après le titre du dossier.
    -> ({"title","video_id"} ou None, remarque)"""
    if kind == "anime":
        return None, ""
    from src import title_lookup
    from src.sources import themerrdb
    key = os.getenv("TMDB_API_KEY", "").strip()
    clean = library.clean_title(series.name)
    ids, why = [], ""
    progress.say("Identifiant TheMovieDB : recherche dans Emby…")
    tid, w = EMBY.tmdb_id(series.name, clean, kind, series.parent.name)
    if tid:
        ids.append(tid)
    else:
        why = w
        progress.say("Titre original (Emby, puis TheMovieDB)…")
        orig, w2 = original_title_for(series, clean, kind)
        for cand in ([orig] if orig else []) + [clean]:
            progress.say(f"Identifiant TheMovieDB : recherche de « {cand} »…")
            t, w3 = title_lookup.tmdb_id(series.name, cand, kind, key)
            if t and t not in ids:
                ids.append(t)
            elif not t:
                why = w3
            if ids and cand == orig:        # le titre original a donné une réponse : on ne devine pas plus loin
                break
    if not ids:
        return None, why or "identifiant TheMovieDB introuvable"
    last = ""
    for tid in ids:
        progress.say(f"ThemerrDB : thème pour l'identifiant {tid}…")
        tr, last = themerrdb.lookup(kind, tid)
        if tr:
            return tr, ""
    return None, f"{last} (identifiant TheMovieDB {', '.join(map(str, ids))})"


def _auto_one(folder, title, series=None, number=None, query=None, kind="anime"):
    """Choisit automatiquement le générique (animes : AnimeThemes ; films et séries : uniquement ThemerrDB), l'enregistre (normalisé) et prévient Emby. -> (succès, message)"""
    series = series or folder
    query = query or (title if number is None else library.season_query(title, number))
    source = source_for(kind)
    with _work_lock:
        mtype = "anime" if kind == "anime" else ("movie" if kind == "movie" else "tv")
        result = None
        if kind != "anime":
            # Films et séries : on n'accepte QUE un thème validé par la communauté (ThemerrDB). Aucun choix automatique
            # sur YouTube (il valide n'importe quoi) : sinon on passe au suivant, la recherche se fait à la main.
            if number is not None:
                return False, "pas de thème validé par la communauté pour une saison : à chercher à la main"
            tr, why = themerr_for(series, kind)
            if not tr:
                return False, f"pas de thème validé par la communauté (ThemerrDB : {why or 'inconnu'}) : à chercher à la main"
            from src.sources.youtube import watch_url
            result = ThemeResult(title=(tr["title"] or title) + " (ThemerrDB)", source="YouTube", url=watch_url(tr["video_id"]))
        else:
            result = source.search(query, mtype)
            if not result and number is None:         # rien sous le titre du dossier : on tente le titre original
                alt, _ = original_title_for(series, title, kind)
                if alt and alt.casefold() != query.casefold():
                    result = source.search(alt, mtype)
            if not result:
                if getattr(source, "api_error", False):
                    return False, f"{TRANSIENT}{source.name} ne répond pas pour le moment : sera retenté au prochain lot"
                return False, f"aucun générique trouvé sur {source.name} pour « {query} »"
            if number is not None:                     # saison : jamais le même thème que la série ou une autre saison
                from src import dupes
                known = dupes.load_sources(SOURCES_FILE)
                if any(known.get(str(f)) == result.url for f, _t in dupes.sibling_themes(series, folder)):
                    return False, f"AnimeThemes n'a pas de fiche propre à la saison {number} (même thème que la série ou une autre saison) : à choisir à la main"
        ok, why = _download_replace(source, result.url, folder, trusted=(kind != "anime"),
                                    forbid_same_as=series if (kind == "anime" and number is not None) else None)   # films/séries : vidéo choisie par ThemerrDB
        if not ok:
            passing = any(k in why for k in ("réessaie", "écriture impossible", "injoignable", "conversion impossible", "403"))
            return False, (TRANSIENT + why) if passing else why     # panne passagère : on retentera ; vidéo trop longue, bloquée… : non
    emby = EMBY.refresh_series(series.name, title, number, kind, series.parent.name)
    return True, f"{result.title} · {emby['message']}"

def _run_normalize():
    """Ramène à TARGET_DB tous les theme.mp3 déjà présents (originaux copiés dans le dossier des anciens thèmes)."""
    try:
        _run_normalize_inner()
    except Exception:                    # ex. NAS qui décroche pendant le parcours : le lot ne reste jamais bloqué « en cours »
        logger.exception("La normalisation s'est arrêtée sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def _run_normalize_inner():
    from src.audio import normalize_file
    files = []
    skipped_other = 0
    movie_roots = [Path(p) for c in CATS if c["kind"] == "movie" for p in c["paths"]]
    for series in library.iter_series_folders(ROOTS):
        is_movie = any(r in series.parents for r in movie_roots)
        extra = [] if is_movie else [(f"saison {n}", f) for n, f in library.season_folders(series)]
        for label, folder in [("film" if is_movie else "série", series)] + extra:
            theme = find_theme(folder)
            if theme is None:
                continue
            if theme.suffix.lower() == ".mp3" and theme.parent == folder:
                files.append((f"{library.clean_title(series.name)} — {label}", theme))
            else:
                skipped_other += 1
    bad = _nas_problem(ROOTS)
    if bad:
        with _batch_lock:
            BATCH.update(kind="normalize", running=True, total=0, done=0, failed=0, current="", messages=[])
        _batch_note(f"⚠️ Partage réseau inaccessible : {bad} — normalisation arrêtée, rien n'a été touché")
        return
    registry = _read_registry()
    backup = _backup_dir() / "normalisation" / f"{datetime.now():%Y%m%d-%H%M%S}"
    with _batch_lock:
        BATCH.update(kind="normalize", running=True, stop=False, total=len(files), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(files)} thème(s) MP3 à vérifier (cible {TARGET_DB:g} dB)" + (f" · {skipped_other} autre(s) format(s) ignoré(s)" if skipped_other else ""))
    changed = already = 0

    def save_registry():
        try:
            NORMALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
            NORMALIZED_FILE.write_text(json.dumps(registry))
        except OSError:
            pass
    try:
        for n_seen, (label, path) in enumerate(files, 1):
            if n_seen % 20 == 0:
                save_registry()     # enregistré au fil de l'eau : un redémarrage (mise à jour) ne fait pas tout refaire
            with _work_lock:                               # jamais pendant un enregistrement en cours dans ce dossier
                for leftover in path.parent.glob("*.partiel"):    # reste d'une copie interrompue (redémarrage en plein travail)
                    try:
                        if time.time() - leftover.stat().st_mtime > 600:
                            leftover.unlink()
                    except OSError:
                        pass
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            with _batch_lock:
                BATCH["current"] = label
            known = registry.get(str(path))
            if isinstance(known, list) and len(known) == 2:
                known = known + [89.0]                         # anciennes entrées : normalisées à 89 dB
            if known == _signature(path) + [TARGET_DB]:
                already += 1
                with _batch_lock:
                    BATCH["done"] += 1
                continue
            try:
                with _work_lock:
                    status, before, after = normalize_file(path, TARGET_DB, backup_dir=backup / _slug(f"{path.parent.parent.name}_{path.parent.name}"))
            except Exception as e:      # un fichier récalcitrant ne doit pas arrêter tout le lot
                logger.exception("Normalisation impossible : %s", path)
                status, before, after = "error", None, None
                _batch_note(f"❌ {label} — {type(e).__name__} : {e}")
                with _batch_lock:
                    BATCH["failed"] += 1
                continue
            if status == "error":
                with _batch_lock:
                    BATCH["failed"] += 1
                _batch_note(f"❌ {label} — mesure ou conversion impossible (voir le Journal)")
                continue
            if status == "done":
                changed += 1
                registry[str(path)] = _signature(path) + [TARGET_DB]
                _batch_note(f"🔊 {label} — {before:.1f} → {after:.1f} dB" if after is not None else f"🔊 {label} normalisé")
            else:
                already += 1
                registry[str(path)] = _signature(path) + [TARGET_DB]
            with _batch_lock:
                BATCH["done"] += 1
        save_registry()
        _batch_note(f"Terminé : {changed} normalisé(s), {already} déjà au bon niveau" + (f" · originaux dans {backup}" if changed else ""))
    except Exception:
        logger.exception("La normalisation s'est arrêtée sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        save_registry()
        with _batch_lock:
            BATCH.update(running=False, current="")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html", version=APP_VERSION, target_db=f"{TARGET_DB:g}")


@app.route("/api/poster")
def api_poster():
    """Poster du titre choisi (celui d'Emby, dans le dossier), pour vérifier qu'on cherche le générique du bon.
    Pour une saison : son poster (« season01-poster.jpg ») s'il existe, sinon celui de la série."""
    _, series, saison = library.resolve_target(ROOTS, request.args.get("id", ""))
    if series is None:
        return jsonify({"error": "Titre introuvable"}), 404
    noms = []
    if saison is not None:
        noms += ["season-specials-poster" if saison == 0 else f"season{saison:02d}-poster"]
    noms += ["poster", "folder", "cover"]
    for nom in noms:
        for ext in ("jpg", "jpeg", "png", "webp"):
            f = series / f"{nom}.{ext}"
            if f.is_file():
                return send_file(f, max_age=86400)
    return jsonify({"error": "Pas de poster"}), 404


@app.route("/api/library")
def api_library():
    items = library.list_library(ROOTS)
    sk = skipped.entries()

    def why(key):
        e = sk.get(key) or {}
        return (f"mis de côté le {e['date'][8:10]}/{e['date'][5:7]}/{e['date'][:4]}" if e.get("date") else "mis de côté") + (f" : {e['reason']}" if e.get("reason") else "")
    for it in items:
        root = int(it["id"].split("/")[0])
        base = Path(ROOTS[root]) / it["name"]
        it["skipped"] = (not it["has_theme"]) and str(base) in sk
        if it["skipped"]:
            it["skip_why"] = why(str(base))
        for se in it["seasons"]:
            se["skipped"] = (not se["has_theme"]) and str(base / se["name"]) in sk
            if se["skipped"]:
                se["skip_why"] = why(str(base / se["name"]))
        it["cat"] = ROOT_CAT[root]
        it["chemin"] = str(base)                    # pour s'ouvrir directement sur ce titre depuis MouFloster (?dossier=…)
        it["origin"] = Path(ROOTS[root]).name      # dossier d'origine (utile quand un onglet regroupe Films HD et Films 4K)
    cats = [{"index": i, "name": c["name"], "kind": c["kind"], "ok": c["ok"], "multi": len(c["paths"]) > 1} for i, c in enumerate(CATS)]
    return jsonify({"items": items, "emby": EMBY.configured, "categories": cats})


def _search_work(body):
    title = str(body.get("title") or "").strip()
    if not title:
        return {"error": "Titre vide"}, 400
    try:
        kind = CATS[int(body.get("cat", 0))]["kind"]
    except (ValueError, IndexError, TypeError):
        kind = "anime"

    titles = [title]
    note = ""
    folder, series, _ = library.resolve_target(ROOTS, body.get("id", ""))
    series_name = series.name if series else ""
    results, seen = [], set()
    if series and kind != "anime":
        progress.say("Consultation de ThemerrDB (thème validé par la communauté)…")
        tr, _why = themerr_for(series, kind)
        if tr and tr["video_id"] in (body.get("exclude") or []):      # vidéo déjà refusée par YouTube au téléchargement
            progress.say("ThemerrDB : thème trouvé, mais YouTube refuse de le télécharger : recherche d'autres vidéos")
            tr, _why = None, "vidéo bloquée"
        progress.say("ThemerrDB : thème trouvé ★" if tr else f"ThemerrDB : rien — {_why or 'raison inconnue'}")
        if tr:
            from src.sources.youtube import watch_url
            seen.add(tr["video_id"])
            results.append({"name": "★ " + (tr["title"] or title), "year": "base ThemerrDB", "channel": "choix validé par la communauté",
                            "score": 100, "themes": [{"slug": "▶", "type": "yt", "youtube": tr["video_id"], "url": watch_url(tr["video_id"])}]})
            if not body.get("full"):         # thème validé par la communauté : inutile de chercher sur YouTube (sauf demande explicite)
                return {"results": results, "source": "ThemerrDB", "queries": [], "themerr_only": True,
                        "note": "", "skipped": False}, 200
    if body.get("original"):
        # titre original d'après Emby / TheMovieDB (le titre français ne donne pas toujours de résultat)
        if series:
            progress.say("Recherche du titre original (Emby, puis TheMovieDB)…")
            orig, why = original_title_for(series, title, kind)
            if orig and orig.casefold() not in (t.casefold() for t in titles):
                titles.insert(0, orig)                    # le titre original a plus de chances d'avoir des sources : on le cherche en premier
            elif orig:
                note = "Le titre original est identique au titre cherché"
            else:
                note = "Titre original non utilisé : " + why

    def run(t):
        if kind == "anime":
            return SOURCE.candidates(t)
        return YOUTUBE.candidates(t, "movie" if kind == "movie" else "series", year=year_of(series_name))

    for i, t in enumerate(titles, 1):
        progress.say(f"Recherche {'AnimeThemes' if kind == 'anime' else 'sur YouTube'} : « {t} »" + (f" ({i}/{len(titles)})" if len(titles) > 1 else "") + "…")
        try:
            found = run(t)
        except Exception:
            if len(titles) == 1:
                raise
            logger.exception("Recherche impossible pour « %s »", t)
            continue
        for r in found:
            key = (r.get("themes") or [{}])[0].get("youtube") if kind != "anime" else r.get("name")
            if key in seen:
                continue
            seen.add(key)
            results.append(r)
    progress.say("Classement des résultats…")
    if not results and folder:
        skipped.add(folder, "recherche sans résultat")             # rien trouvé : mis de côté, pour ne plus le voir dans la liste « sans thème »
    results.sort(key=lambda r: -int(r.get("score") or 0))     # la sélection ThemerrDB (score 100) reste en tête
    return {"results": results[:12], "source": "AnimeThemes" if kind == "anime" else "YouTube", "queries": titles, "note": note,
            "skipped": bool(not results and folder)}, 200


@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.get_json(silent=True) or {}
    return jsonify({"job": progress.start(lambda: _search_work(body))})


@app.route("/api/job/<jid>")
def api_job(jid):
    st = progress.status(jid, request.args.get("since", 0, type=int) or 0)
    if st is None:
        return jsonify({"error": "Opération inconnue (l'appli a peut-être redémarré)"}), 404
    return jsonify(st)


@app.route("/api/job/<jid>/cancel", methods=["POST"])
def api_job_cancel(jid):
    return jsonify({"ok": progress.cancel(jid)})


def _save_work(data):
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    url = data.get("url", "")
    if not folder:
        return {"error": "Série ou saison introuvable"}, 404
    kind = kind_of(data.get("id", ""))
    source = source_for(kind)
    if not source.is_allowed_url(url):
        return {"error": "Adresse non autorisée (seuls animethemes.moe et youtube.com sont acceptés)"}, 400
    if _work_lock.locked():
        progress.say("En attente : un autre traitement est en cours…")
    with _work_lock:
        ok, why = _download_replace(source, url, folder, trusted=bool(data.get("trusted")))
        if not ok:
            return {"error": "Thème non enregistré : " + why + ". L'ancien thème (s'il y en avait un) est conservé."}, 502
        progress.say("Mise à jour d'Emby…")
        emby = EMBY.refresh_series(series.name, data.get("title", ""), number, kind, series.parent.name)
    logger.info("Thème enregistré : %s", folder / THEME_FILENAME)
    skipped.remove(folder)
    return {"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]}, 200


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    return jsonify({"job": progress.start(lambda: _save_work(data))})



# ---------- thème personnalisé : un lien (YouTube ou autre site pris en charge par yt-dlp) ou un fichier audio de l'utilisateur ----------
AUDIO_EXTS = (".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wav", ".wma", ".mp4", ".webm", ".mka")
MAX_UPLOAD = 150 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD + 1024 * 1024      # vraie limite, même sans taille annoncée par le navigateur


@app.errorhandler(413)
def _too_big(_e):
    return jsonify({"error": "Fichier trop gros (150 Mo maximum)"}), 413


def _public_url(url):
    """http(s) vers un site public uniquement (pas d'adresse locale ou privée : l'appli ne sert pas à atteindre le réseau de la maison). -> message d'erreur ou ''"""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    u = urlparse(url or "")
    if u.scheme not in ("http", "https") or not u.hostname:
        return "Adresse invalide : colle un lien complet commençant par https://"
    try:
        for info in socket.getaddrinfo(u.hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return "Adresse refusée : elle pointe vers le réseau local."
    except (socket.gaierror, ValueError):
        return "Adresse introuvable (vérifie le lien)."
    return ""


def _custom_url_work(data):
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return {"error": "Série ou saison introuvable"}, 404
    url = str(data.get("url", "")).strip()
    bad = _public_url(url)
    if bad:
        return {"error": bad}, 400
    kind = kind_of(data.get("id", ""))
    if _work_lock.locked():
        progress.say("En attente : un autre traitement est en cours…")
    with _work_lock:
        ok, why = _download_replace(YOUTUBE, YOUTUBE.canonical_url(url), folder, trusted=True, any_url=True)
        if not ok:
            return {"error": "Thème non enregistré : " + why + ". L'ancien thème (s'il y en avait un) est conservé."}, 502
        progress.say("Mise à jour d'Emby…")
        emby = EMBY.refresh_series(series.name, data.get("title", ""), number, kind, series.parent.name)
    logger.info("Thème personnalisé (lien) enregistré : %s", folder / THEME_FILENAME)
    skipped.remove(folder)
    return {"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]}, 200


def _custom_file_work(item_id, title, tmp_src, original_name, trim=True):
    from src.audio import convert_to_mp3
    folder, series, number = library.resolve_target(ROOTS, item_id)
    try:
        if not folder:
            return {"error": "Série ou saison introuvable"}, 404
        kind = kind_of(item_id)
        if _work_lock.locked():
            progress.say("En attente : un autre traitement est en cours…")
        with _work_lock:
            import tempfile
            progress.say("Conversion en MP3 et réglage du volume…")
            with tempfile.TemporaryDirectory() as work:
                out = Path(work) / "theme.mp3"                       # ffmpeg déduit le format de l'extension
                if not convert_to_mp3(Path(tmp_src), out, TARGET_DB):
                    return {"error": "Ce fichier n'a pas pu être lu comme un son (détails : bouton Journal). L'ancien thème est conservé."}, 502
                tmp = folder / "theme.nouveau.partiel"               # copié à côté d'abord : le thème en place n'est touché qu'une fois le nouveau prêt
                _clear_partials(folder)
                try:
                    safe_move(out, tmp)
                    if trim:
                        _maybe_trim(tmp)
                    progress.say("Mise en place du thème (l'ancien est mis de côté)…")
                    _install_theme(tmp, folder)
                except OSError as e:
                    logger.error("Écriture impossible dans %s : %s", folder, e)
                    try:
                        tmp.unlink()
                    except OSError:
                        pass
                    return {"error": "Thème non enregistré : " + _write_problem(folder, e) + ". L'ancien thème est conservé."}, 502
            from src import dupes
            dupes.remember_source(SOURCES_FILE, folder, "fichier : " + original_name)
            progress.say("Mise à jour d'Emby…")
            emby = EMBY.refresh_series(series.name, title, number, kind, series.parent.name)
        logger.info("Thème personnalisé (fichier « %s ») enregistré : %s", original_name, folder / THEME_FILENAME)
        skipped.remove(folder)
        return {"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]}, 200
    finally:
        try:
            os.unlink(tmp_src)
        except OSError:
            pass


@app.route("/api/custom/url", methods=["POST"])
def api_custom_url():
    data = request.get_json(silent=True) or {}
    return jsonify({"job": progress.start(lambda: _custom_url_work(data))})


@app.route("/api/custom/file", methods=["POST"])
def api_custom_file():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "Aucun fichier reçu"}), 400
    if not f.filename.lower().endswith(AUDIO_EXTS):
        return jsonify({"error": "Format non pris en charge (mp3, m4a, flac, ogg, wav…)"}), 400
    if (request.content_length or 0) > MAX_UPLOAD:
        return jsonify({"error": "Fichier trop gros (150 Mo maximum)"}), 413
    import tempfile
    fd, tmp_src = tempfile.mkstemp(suffix=Path(f.filename).suffix.lower())
    os.close(fd)
    f.save(tmp_src)
    item_id, title, name = request.form.get("id", ""), request.form.get("title", ""), Path(f.filename).name
    return jsonify({"job": progress.start(lambda: _custom_file_work(item_id, title, tmp_src, name))})


# ---------- éditeur audio : découper et ajouter des fondus avant d'enregistrer ----------
from src import audioedit


def _stage_work(item_id, kind_src, url=None, upload=None, upload_name=""):
    """Prépare la copie de travail (thème actuel, lien ou fichier envoyé). -> ({token, duration, name}, 200) ou erreur"""
    import tempfile
    folder, series, number = library.resolve_target(ROOTS, item_id)
    try:
        if not folder:
            return {"error": "Série ou saison introuvable"}, 404
        with tempfile.TemporaryDirectory() as work:
            if kind_src == "current":
                cur = find_theme(folder)
                if not cur:
                    return {"error": "Pas de thème à éditer"}, 404
                src, label = cur, "thème actuel"
            elif kind_src == "file":
                src, label = Path(upload), upload_name
            else:
                bad = _public_url(url)
                if bad:
                    return {"error": bad}, 400
                src = Path(work) / "source.mp3"
                source = SOURCE if SOURCE.is_allowed_url(url) else YOUTUBE
                with _work_lock:
                    ok = (YOUTUBE.download(YOUTUBE.canonical_url(url), src, trusted=True, any_url=True) if source is YOUTUBE
                          else source.download(url, src))
                if not ok:
                    return {"error": "Téléchargement impossible : " + (getattr(source, "last_error", "") or "détails dans le Journal")}, 502
                label = "lien"
            progress.say("Préparation de la courbe du son…")
            st = audioedit.stage(BASE_DIR, src)
        if not st:
            return {"error": "Ce fichier n'a pas pu être lu comme un son (détails : bouton Journal)."}, 502
        return {**st, "name": label}, 200
    finally:
        if upload:
            try:
                os.unlink(upload)
            except OSError:
                pass


@app.route("/api/edit/stage", methods=["POST"])
def api_edit_stage():
    data = request.get_json(silent=True) or {}
    item_id, src, url = data.get("id", ""), data.get("source", "current"), str(data.get("url", "")).strip()
    return jsonify({"job": progress.start(lambda: _stage_work(item_id, src, url))})


@app.route("/api/edit/stage-file", methods=["POST"])
def api_edit_stage_file():
    f = request.files.get("file")
    if not f or not f.filename or not f.filename.lower().endswith(AUDIO_EXTS):
        return jsonify({"error": "Choisis un fichier audio (mp3, m4a, flac, ogg, wav…)"}), 400
    if (request.content_length or 0) > MAX_UPLOAD:
        return jsonify({"error": "Fichier trop gros (150 Mo maximum)"}), 413
    import tempfile
    fd, tmp_src = tempfile.mkstemp(suffix=Path(f.filename).suffix.lower())
    os.close(fd)
    f.save(tmp_src)
    item_id, name = request.form.get("id", ""), Path(f.filename).name
    return jsonify({"job": progress.start(lambda: _stage_work(item_id, "file", None, tmp_src, name))})


def _edit_path(token, ext):
    if not audioedit.valid_token(token):
        return None
    p = audioedit.edit_dir(BASE_DIR) / f"{token}.{ext}"
    return p if p.is_file() else None


@app.route("/api/edit/<token>/peaks")
def api_edit_peaks(token):
    p = _edit_path(token, "json")
    if not p:
        return jsonify({"error": "Copie de travail expirée : recommence l'édition"}), 404
    return send_file(p, mimetype="application/json")


@app.route("/api/edit/<token>/audio")
def api_edit_audio(token):
    p = _edit_path(token, "mp3")
    if not p:
        return jsonify({"error": "Copie de travail expirée"}), 404
    return send_file(p, mimetype="audio/mpeg", conditional=True)


def _edit_save_work(token, item_id, title, start, end, fade_in, fade_out):
    import tempfile
    src = _edit_path(token, "mp3")
    if not src:
        return {"error": "Copie de travail expirée : recommence l'édition"}, 404
    total = audioedit.duration(src) or 0
    start, end = max(0.0, start), min(total, end) if total else end
    if end - start < 1.0:
        return {"error": "La partie gardée doit durer au moins 1 seconde"}, 400
    half = (end - start) / 2
    fade_in, fade_out = min(max(0.0, fade_in), half), min(max(0.0, fade_out), half)
    fd, tmp = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    progress.say("Découpe et fondus…")
    if not audioedit.render(src, Path(tmp), start, end, fade_in, fade_out):
        os.unlink(tmp)
        return {"error": "La découpe a échoué (détails : bouton Journal)"}, 502
    res = _custom_file_work(item_id, title, tmp, f"édité ({end - start:.1f} s)", trim=False)      # déjà coupé à la main ; conversion, volume, mise en place, Emby (supprime tmp)
    if res[1] == 200:
        for ext in ("mp3", "json"):
            try:
                (audioedit.edit_dir(BASE_DIR) / f"{token}.{ext}").unlink()
            except OSError:
                pass
    return res


@app.route("/api/edit/<token>/save", methods=["POST"])
def api_edit_save(token):
    d = request.get_json(silent=True) or {}
    try:
        start, end, fi, fo = (float(d.get(k, 0) or 0) for k in ("start", "end", "fade_in", "fade_out"))
    except (TypeError, ValueError):
        return jsonify({"error": "Valeurs invalides"}), 400
    if not audioedit.valid_token(token):
        return jsonify({"error": "Copie de travail inconnue"}), 404
    return jsonify({"job": progress.start(lambda: _edit_save_work(token, d.get("id", ""), d.get("title", ""), start, end, fi, fo))})


@app.route("/api/duplicates")
def api_duplicates():
    from src import dupes
    movie_roots = {i for i, c in enumerate(ROOT_CAT) if CATS[c]["kind"] == "movie"}
    found = dupes.find_duplicates(ROOTS, movie_roots)
    return jsonify({"series": found, "seasons": sum(len(x["dups"]) for x in found)})


@app.route("/api/duplicates/fix", methods=["POST"])
def api_duplicates_fix():
    """Remet des saisons dans « sans thème » : leur thème en double est mis de côté (jamais supprimé)."""
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    n = 0
    with _work_lock:
        for item_id in ids:
            folder, series, number = library.resolve_target(ROOTS, str(item_id))
            if not folder or number is None or not find_theme(folder):
                continue
            _backup_existing(folder)
            skipped.remove(folder)
            if not find_theme(folder):
                n += 1
    logger.info("Doublons de saisons : %d thème(s) mis de côté", n)
    return jsonify({"ok": True, "count": n})


@app.route("/api/skipped/retry", methods=["POST"])
def api_skipped_retry():
    """« Réessayer les mis de côté » d'un onglet : ils reviennent dans « sans thème » et seront recherchés au prochain lot."""
    try:
        cat = int((request.get_json(silent=True) or {}).get("cat", 0))
        roots = CATS[cat]["paths"]
    except (ValueError, IndexError, TypeError):
        return jsonify({"error": "Médiathèque inconnue"}), 400
    n = skipped.clear_under(roots)
    logger.info("Mis de côté remis à chercher (%s) : %d", CATS[cat]["name"], n)
    return jsonify({"ok": True, "count": n})


@app.route("/api/skip", methods=["POST"])
def api_skip():
    data = request.get_json(silent=True) or {}
    folder, _series, _n = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    if data.get("skip", True):
        skipped.add(folder, "mis de côté à la main")
    else:
        skipped.remove(folder)
    return jsonify({"ok": True})


@app.route("/api/theme/delete", methods=["POST"])
def api_theme_delete():
    """Supprime le thème d'un titre : double validation obligatoire. Le fichier n'est pas détruit, il est mis de côté dans le dossier des anciens thèmes."""
    data = request.get_json(silent=True) or {}
    if data.get("confirm") != 2:
        return jsonify({"error": "Double validation manquante : rien n'a été supprimé."}), 400
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    if not find_theme(folder):
        return jsonify({"error": "Ce titre n'a pas de thème"}), 404
    with _work_lock:
        _backup_existing(folder)
    if find_theme(folder):
        return jsonify({"error": "Le thème n'a pas pu être supprimé (droits d'écriture ? détails : bouton Journal)"}), 500
    logger.info("Thème supprimé (mis de côté) : %s", folder)
    kind = kind_of(data.get("id", ""))
    emby = EMBY.refresh_series(series.name, library.clean_title(series.name), number, kind, series.parent.name)
    return jsonify({"ok": True, "message": f"Thème supprimé (l'ancien fichier est conservé dans le dossier des anciens thèmes). {emby['message']}"})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.get_json(silent=True) or {}
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    title = library.clean_title(series.name)
    query = (data.get("title") or "").strip() or None      # titre éventuellement corrigé à la main dans la page
    ok, msg = _auto_one(folder, title, series, number, query, kind_of(data.get("id", "")))
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 404)


@app.route("/api/theme")
def api_theme():
    folder = library.resolve_folder(ROOTS, request.args.get("id", ""))
    path = find_theme(folder) if folder else None
    if not path:
        return jsonify({"error": "Pas de thème"}), 404
    return send_file(path, mimetype=mimetypes.guess_type(path.name)[0] or "audio/mpeg", conditional=True)


# ---------- anciens thèmes : écouter, restaurer ----------
_BACKUP_RE = re.compile(r"^(\d{8})-(\d{6})_(.+)\.mp3$")


def _backups_of(folder):
    """Anciens thèmes MP3 de ce dossier dans le dossier des anciens thèmes, du plus récent au plus ancien."""
    key = f"{_slug(folder.parent.name)}_{_slug(folder.name)}"
    out = []
    try:
        for f in _backup_dir().iterdir():
            m = _BACKUP_RE.match(f.name)
            rest = m.group(3) if m else ""          # « <clé> » ou « <clé>_2 » (deux sauvegardes dans la même seconde)
            if m and (rest == key or (rest.startswith(key + "_") and rest[len(key) + 1:].isdigit())) and f.is_file():
                d, t = m.group(1), m.group(2)
                out.append({"name": f.name, "date": f"{d[6:8]}/{d[4:6]}/{d[:4]} {t[:2]}:{t[2:4]}", "size": f.stat().st_size, "sort": f.name})
    except OSError:
        pass
    out.sort(key=lambda b: b["sort"], reverse=True)
    return out


@app.route("/api/backups")
def api_backups():
    folder = library.resolve_folder(ROOTS, request.args.get("id", ""))
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    return jsonify({"backups": _backups_of(folder)})


@app.route("/api/backups/file")
def api_backup_file():
    name = Path(request.args.get("name", "")).name                 # jamais de chemin : seulement un nom du dossier des anciens thèmes
    if not _BACKUP_RE.match(name):
        return jsonify({"error": "Fichier inconnu"}), 404
    path = _backup_dir() / name
    if not path.is_file():
        return jsonify({"error": "Fichier introuvable"}), 404
    return send_file(path, mimetype="audio/mpeg", conditional=True)


def _restore_work(item_id, name, title):
    folder, series, number = library.resolve_target(ROOTS, item_id)
    if not folder:
        return {"error": "Série ou saison introuvable"}, 404
    if not any(b["name"] == name for b in _backups_of(folder)):          # seulement un ancien thème de CE titre
        return {"error": "Cet ancien thème n'appartient pas à ce titre"}, 400
    src = _backup_dir() / name
    if _work_lock.locked():
        progress.say("En attente : un autre traitement est en cours…")
    with _work_lock:
        progress.say("Remise en place de l'ancien thème (l'actuel est mis de côté)…")
        tmp = folder / "theme.nouveau.partiel"
        _clear_partials(folder)
        try:
            safe_copy(src, tmp)                    # COPIE : l'ancien thème reste aussi dans les anciens thèmes
            _install_theme(tmp, folder)
        except OSError as e:
            logger.error("Restauration impossible dans %s : %s", folder, e)
            try:
                tmp.unlink()
            except OSError:
                pass
            return {"error": "Thème non restauré : " + _write_problem(folder, e) + ". Le thème actuel est conservé."}, 502
        from src import dupes
        dupes.remember_source(SOURCES_FILE, folder, "restauré : " + name)
        progress.say("Mise à jour d'Emby…")
        emby = EMBY.refresh_series(series.name, title, number, kind_of(item_id), series.parent.name)
    logger.info("Ancien thème restauré (%s) : %s", name, folder / THEME_FILENAME)
    skipped.remove(folder)
    return {"ok": True, "message": f"Ancien thème remis en place. {emby['message']}", "emby_ok": emby["ok"]}, 200


@app.route("/api/backups/restore", methods=["POST"])
def api_backup_restore():
    data = request.get_json(silent=True) or {}
    item_id, name, title = str(data.get("id", "")), Path(str(data.get("name", ""))).name, str(data.get("title", ""))
    return jsonify({"job": progress.start(lambda: _restore_work(item_id, name, title))})


@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    body = request.get_json(silent=True) or {}
    with_seasons = bool(body.get("seasons"))
    try:
        cat = int(body.get("cat", 0))
        CATS[cat]
    except (ValueError, IndexError, TypeError):
        return jsonify({"error": "Médiathèque inconnue"}), 400
    try:
        limit = int(body["limit"]) if body.get("limit") else None
    except (ValueError, TypeError):
        return jsonify({"error": "Nombre maximum invalide"}), 400
    with _batch_lock:   # on marque « en cours » tout de suite : la page qui interroge juste après le voit
        if BATCH["running"]:
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        BATCH.update(running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_batch, args=(limit, with_seasons, cat), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/normalize/start", methods=["POST"])
def api_normalize_start():
    with _batch_lock:
        if BATCH["running"]:
            return jsonify({"error": "Un traitement est déjà en cours"}), 409
        BATCH.update(kind="normalize", running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_normalize, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/batch/stop", methods=["POST"])
def api_batch_stop():
    BATCH["stop"] = True
    return jsonify({"ok": True})


@app.route("/api/batch/status")
def api_batch_status():
    with _batch_lock:
        return jsonify(dict(BATCH))


os.environ['_TARGET_DB'] = f'{TARGET_DB:g}'
import emby_settings


def _emby_key_changed(key):
    EMBY.api_key = key


for _i, _c in enumerate(CATS):
    logger.info("Onglet %s : %s", _c["name"], " + ".join(_c["paths"]))
if IGNORED_FOLDERS:
    logger.info("Dossiers ignorés (type non reconnu) : %s — à ajouter dans config.json (library.categories) si besoin", ", ".join(IGNORED_FOLDERS))
try:
    _migrate_old_backups()
except Exception:
    logger.exception("Migration des anciennes sauvegardes impossible")
emby_settings.init_app(app, BASE_DIR, lambda: EMBY.host, _emby_key_changed)
import tmdb_settings
tmdb_settings.init_app(app, BASE_DIR)
diag.init_app(app, APP_VERSION, lambda: ROOTS, EMBY.describe, _batch_state_text)

def _clean_stale_partials():
    """Un redémarrage (mise à jour) pendant un téléchargement laisse un « theme.nouveau.partiel » : on retire ceux de plus de 10 minutes."""
    import time
    n = 0
    try:
        for root in ROOTS:
            for series in Path(root).iterdir():
                if not series.is_dir():
                    continue
                for folder in [series] + [p for _n, p in library.season_folders(series)]:
                    part = folder / "theme.nouveau.partiel"
                    try:
                        if part.is_file() and time.time() - part.stat().st_mtime > 600:
                            part.unlink(); n += 1
                    except OSError:
                        pass
    except OSError:
        pass
    if n:
        logger.info("Fichiers partiels abandonnés supprimés : %d", n)


threading.Thread(target=_clean_stale_partials, daemon=True).start()

# ---------- lot de nuit + compte rendu Telegram ----------
import nightly_settings
from src import nightly
nightly.init(BASE_DIR / "data" / "nightly.json")


def _nightly_run():
    """Cherche les thèmes manquants de tous les onglets, puis envoie le compte rendu par Telegram."""
    with _batch_lock:
        if BATCH["running"]:
            return
        BATCH.update(kind="download", running=True, stop=False, total=0, done=0, failed=0, current="Lot de nuit…", messages=[])
    t0, by_cat = time.time(), []
    try:
        for i, c in enumerate(CATS):
            if BATCH["stop"]:                       # « Arrêter » arrête tout le lot de nuit, pas seulement l'onglet en cours
                break
            with _batch_lock:
                BATCH["running"] = True
            by_cat.append(_run_batch(None, c["kind"] == "anime" and nightly.settings()["seasons"], i, fresh=(i == 0)))
    except Exception:
        logger.exception("Lot de nuit interrompu")
    text = nightly.format_report(by_cat, time.time() - t0)
    summary = f"{sum(len(c['added']) for c in by_cat)} ajouté(s), {sum(c['failed'] for c in by_cat)} sans thème"
    nightly.save(last_summary=f"{datetime.now():%d/%m %H:%M} : {summary}")
    logger.info("[nuit] Lot terminé : %s", summary)
    if text:
        ok, msg = nightly.send(text)
        logger.info("[nuit] Telegram : %s", msg)


nightly_settings.init_app(app, BASE_DIR, nightly, lambda: threading.Thread(target=_nightly_run, daemon=True).start(), lambda: bool(BATCH.get("running")))

import redemarrage      # alerte Telegram après un plantage ou un redémarrage du serveur
redemarrage.init_app(app, BASE_DIR)
import settings_page


AUTO_TRIM = {"auto_trim": bool(CONFIG.get("audio", {}).get("auto_trim", False)),
             "trim_max": int(CONFIG.get("audio", {}).get("trim_max", 90)), "trim_fade": float(CONFIG.get("audio", {}).get("trim_fade", 3))}


def _maybe_trim(path):
    """Coupe automatique (réglage) : un thème plus long que la durée maximale est coupé, avec un fondu de sortie.
    Jamais pour l'éditeur (déjà coupé à la main), ni pour la normalisation ou une restauration."""
    if not AUTO_TRIM["auto_trim"]:
        return False
    from src.audio import convert_to_mp3
    import tempfile
    try:
        length = audioedit.duration(path)
    except Exception:
        return False
    mx, fade = AUTO_TRIM["trim_max"], AUTO_TRIM["trim_fade"]
    if not length or length <= mx + 0.5:
        return False
    progress.say(f"Thème de {int(length)} s : coupé à {mx} s avec un fondu de sortie…")
    with tempfile.TemporaryDirectory() as work:
        cut, out = Path(work) / "cut.wav", Path(work) / "theme.mp3"
        if not (audioedit.render(path, cut, 0.0, float(mx), 0.0, float(fade)) and convert_to_mp3(cut, out, TARGET_DB)):
            logger.warning("Coupe automatique impossible pour %s : thème gardé entier", path)
            return False
        safe_copy(out, path)
    logger.info("Coupe automatique : %s ramené de %d s à %d s", path.parent, int(length), mx)
    return True


def _set_target_db(value):
    global TARGET_DB
    TARGET_DB = float(value)
    SOURCE.target_db = YOUTUBE.target_db = TARGET_DB
    os.environ['_TARGET_DB'] = f'{TARGET_DB:g}'


settings_page.init_app(app, BASE_DIR, lambda: APP_VERSION, lambda: CONFIG, lambda: CATS, lambda: IGNORED_FOLDERS, EMBY,
                       "/mnt/mouflosyno/MouFlopening/Anciens thèmes", get_db=lambda: TARGET_DB, set_db=_set_target_db,
                       get_trim=lambda: dict(AUTO_TRIM), set_trim=AUTO_TRIM.update)
threading.Thread(target=nightly.loop, args=(_nightly_run, lambda: bool(BATCH.get("running"))), daemon=True).start()
from src.sources import youtube as _yt_module
threading.Thread(target=_yt_module.auto_update_loop, args=(lambda: bool(BATCH.get("running")) or _work_lock.locked(),), daemon=True).start()


if __name__ == "__main__":
    redemarrage.verifier(BASE_DIR, "MouFlopening", BASE_DIR / "data" / "mouflopening.log", lambda t: nightly.send(t))
    app.run(debug=False, host="0.0.0.0", port=8001)
