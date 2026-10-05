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
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from src.config import load_config, load_secrets_env

BASE_DIR = Path(__file__).resolve().parent
load_secrets_env()   # identifiants et clé Emby (data/secrets.env), avant l'initialisation de la connexion

from src import library
from src.emby_client import EmbyClient
from src.fsutil import safe_move
from src.library import THEME_DIR, THEME_EXTS, THEME_FILENAME, find_theme
from src.sources.animethemes import AnimeThemesSource
from src.sources.youtube import YouTubeSource

BASE_VERSION = "0.2"


def get_version():
    try:
        count = subprocess.check_output(["git", "rev-list", "--count", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        short = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, text=True, stderr=subprocess.DEVNULL).strip()
        return f"v{BASE_VERSION}.{count} ({short})"
    except Exception:
        return f"v{BASE_VERSION}"


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


def _slug(text):
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:80] or "theme"


def _backup_existing(folder):
    """Avant de poser un nouveau thème, l'ancien (theme.mp3 ou theme.flac, ogg…) est mis de côté, jamais supprimé."""
    for ext in THEME_EXTS:
        old = folder / f"theme{ext}"
        if old.is_file():
            dest = _backup_dir()
            name = f"{datetime.now():%Y%m%d-%H%M%S}_{_slug(folder.parent.name)}_{_slug(folder.name)}{ext}"
            safe_move(old, dest / name)
            logger.info("Ancien thème mis de côté : %s", dest / name)


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
        BATCH["messages"] = (BATCH["messages"] + [text])[-40:]


def _batch_state_text():
    with _batch_lock:
        b = dict(BATCH)
    if not b["running"] and not b["total"]:
        return "aucun lot lancé depuis le démarrage"
    return (f"{'EN COURS' if b['running'] else 'terminé'} · {b['done'] + b['failed']}/{b['total']} "
            f"(ajoutés {b['done']}, introuvables {b['failed']}) · en cours : {b['current'] or '-'}")


def _run_batch(limit, with_seasons, cat=0):
    kind = CATS[cat]["kind"]
    roots = list(CATS[cat]["paths"])
    todo = [("film" if kind == "movie" else "série", title, folder, folder, None) for title, folder in library.missing_themes(roots)]
    if with_seasons and kind != "movie":
        todo += [(f"saison {n}", title, folder, series, n) for title, n, folder, series in library.missing_season_themes(roots)]
    if limit:
        todo = todo[:limit]
    with _batch_lock:
        BATCH.update(kind="download", running=True, stop=False, total=len(todo), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(todo)} thème(s) à chercher" + (" (séries et saisons)" if with_seasons else " (séries)"))
    try:
        for _what, title, folder, series, number in todo:
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            label = title if number is None else f"{title} — saison {number}"
            with _batch_lock:
                BATCH["current"] = label
            ok, msg = _auto_one(folder, title, series, number, kind=kind)   # kind = type de l'onglet (anime / série / film)
            with _batch_lock:
                BATCH["done" if ok else "failed"] += 1
            _batch_note(("✅ " if ok else "❌ ") + f"{label} — {msg}")
    except Exception:
        logger.exception("Le lot s'est arrêté sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def _auto_one(folder, title, series=None, number=None, query=None, kind="anime"):
    """Choisit automatiquement le meilleur générique, l'enregistre (normalisé) et prévient Emby. -> (succès, message)"""
    series = series or folder
    query = query or (title if number is None else library.season_query(title, number))
    source = source_for(kind)
    with _work_lock:
        result = source.search(query, "anime" if kind == "anime" else ("movie" if kind == "movie" else "tv"))
        if not result:
            return False, f"aucun générique trouvé sur {source.name} pour « {query} »"
        _backup_existing(folder)
        if not source.download(result.url, folder / THEME_FILENAME):
            return False, "téléchargement ou conversion impossible (voir le Journal)"
    emby = EMBY.refresh_series(series.name, title, number, kind, series.parent.name)
    return True, f"{result.title} · {emby['message']}"

def _run_normalize():
    """Ramène à TARGET_DB tous les theme.mp3 déjà présents (originaux copiés dans le dossier des anciens thèmes)."""
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
            for leftover in path.parent.glob("*.partiel"):    # reste d'une copie interrompue (redémarrage en plein travail)
                try:
                    leftover.unlink()
                except OSError:
                    pass
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            with _batch_lock:
                BATCH["current"] = label
            if registry.get(str(path)) == _signature(path):
                already += 1
                with _batch_lock:
                    BATCH["done"] += 1
                continue
            try:
                with _work_lock:
                    status, before, after = normalize_file(path, TARGET_DB, backup_dir=backup / _slug(label))
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
                registry[str(path)] = _signature(path)
                _batch_note(f"🔊 {label} — {before:.1f} → {after:.1f} dB" if after is not None else f"🔊 {label} normalisé")
            else:
                already += 1
                registry[str(path)] = _signature(path)
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


@app.route("/api/library")
def api_library():
    items = library.list_library(ROOTS)
    for it in items:
        root = int(it["id"].split("/")[0])
        it["cat"] = ROOT_CAT[root]
        it["origin"] = Path(ROOTS[root]).name      # dossier d'origine (utile quand un onglet regroupe Films HD et Films 4K)
    cats = [{"index": i, "name": c["name"], "kind": c["kind"], "ok": c["ok"], "multi": len(c["paths"]) > 1} for i, c in enumerate(CATS)]
    return jsonify({"items": items, "emby": EMBY.configured, "categories": cats})


@app.route("/api/search", methods=["POST"])
def api_search():
    body = request.get_json(silent=True) or {}
    title = body.get("title", "").strip()
    if not title:
        return jsonify({"error": "Titre vide"}), 400
    try:
        kind = CATS[int(body.get("cat", 0))]["kind"]
    except (ValueError, IndexError):
        kind = "anime"

    titles = [title]
    if body.get("original"):
        # titre original d'après Emby (le titre français ne donne pas toujours de résultat)
        folder, series, _ = library.resolve_target(ROOTS, body.get("id", ""))
        if series:
            orig = EMBY.original_title(series.name, title, kind, series.parent.name)
            if orig and orig.casefold() not in (t.casefold() for t in titles):
                titles.append(orig)

    def run(t):
        if kind == "anime":
            return SOURCE.candidates(t)
        return YOUTUBE.candidates(t, "movie" if kind == "movie" else "series")

    results, seen = [], set()
    for t in titles:
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
    results.sort(key=lambda r: -int(r.get("score") or 0))
    return jsonify({"results": results[:8], "source": "AnimeThemes" if kind == "anime" else "YouTube", "queries": titles})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    url = data.get("url", "")
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    kind = kind_of(data.get("id", ""))
    source = source_for(kind)
    if not source.is_allowed_url(url):
        return jsonify({"error": "Adresse non autorisée (seuls animethemes.moe et youtube.com sont acceptés)"}), 400
    with _work_lock:
        _backup_existing(folder)
        ok = source.download(url, folder / THEME_FILENAME)
    if not ok:
        return jsonify({"error": "Téléchargement ou conversion impossible (détails : bouton Journal)"}), 502
    emby = EMBY.refresh_series(series.name, data.get("title", ""), number, kind, series.parent.name)
    logger.info("Thème enregistré : %s", folder / THEME_FILENAME)
    return jsonify({"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]})


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


@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    body = request.get_json(silent=True) or {}
    limit, with_seasons = body.get("limit"), bool(body.get("seasons"))
    try:
        cat = int(body.get("cat", 0))
        CATS[cat]
    except (ValueError, IndexError):
        return jsonify({"error": "Médiathèque inconnue"}), 400
    with _batch_lock:   # on marque « en cours » tout de suite : la page qui interroge juste après le voit
        if BATCH["running"]:
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        BATCH.update(running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_batch, args=(int(limit) if limit else None, with_seasons, cat), daemon=True).start()
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
diag.init_app(app, APP_VERSION, lambda: ROOTS, EMBY.describe, _batch_state_text)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8001)
