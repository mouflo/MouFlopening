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
from src.library import THEME_DIR, THEME_EXTS, THEME_FILENAME, find_theme
from src.sources.animethemes import AnimeThemesSource

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
ROOTS = CONFIG.get("library", {}).get("paths", [])
EMBY = EmbyClient(CONFIG.get("emby", {}))
TARGET_DB = float(CONFIG.get("audio", {}).get("target_db", 89))   # niveau de chaque thème (référence ReplayGain / MP3Gain)
SOURCE = AnimeThemesSource(CONFIG.get("sources", {}).get("animethemes", {"enabled": True}),
                           threshold=CONFIG.get("matching", {}).get("threshold", 70), target_db=TARGET_DB)

app = Flask(__name__)

import auth
import diag

diag.setup_logging()
logger = logging.getLogger("mouflopening")
auth.init_app(app, APP_VERSION)

_work_lock = threading.Lock()   # un seul téléchargement/conversion à la fois (ménage le NAS et le CPU)

BACKUP_DIR = BASE_DIR / "data" / "themes-backup"
NORMALIZED_FILE = BASE_DIR / "data" / "normalized.json"


def _slug(text):
    return re.sub(r"[^\w.-]+", "_", text).strip("_")[:80] or "theme"


def _backup_existing(folder):
    """Avant de poser un nouveau thème, l'ancien (theme.mp3 ou theme.flac, ogg…) est mis de côté, jamais supprimé."""
    for ext in THEME_EXTS:
        old = folder / f"theme{ext}"
        if old.is_file():
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            name = f"{datetime.now():%Y%m%d-%H%M%S}_{_slug(folder.parent.name)}_{_slug(folder.name)}{ext}"
            shutil.move(str(old), str(BACKUP_DIR / name))
            logger.info("Ancien thème mis de côté : %s", BACKUP_DIR / name)


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


def _run_batch(limit, with_seasons):
    todo = [("série", title, folder, folder, None) for title, folder in library.missing_themes(ROOTS)]
    if with_seasons:
        todo += [(f"saison {n}", title, folder, series, n) for title, n, folder, series in library.missing_season_themes(ROOTS)]
    if limit:
        todo = todo[:limit]
    with _batch_lock:
        BATCH.update(kind="download", running=True, stop=False, total=len(todo), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(todo)} thème(s) à chercher" + (" (séries et saisons)" if with_seasons else " (séries)"))
    try:
        for kind, title, folder, series, number in todo:
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            label = title if number is None else f"{title} — saison {number}"
            with _batch_lock:
                BATCH["current"] = label
            ok, msg = _auto_one(folder, title, series, number)
            with _batch_lock:
                BATCH["done" if ok else "failed"] += 1
            _batch_note(("✅ " if ok else "❌ ") + f"{label} — {msg}")
    except Exception:
        logger.exception("Le lot s'est arrêté sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def _auto_one(folder, title, series=None, number=None, query=None):
    """Choisit automatiquement le meilleur générique, l'enregistre (normalisé) et prévient Emby. -> (succès, message)"""
    series = series or folder
    query = query or (title if number is None else library.season_query(title, number))
    with _work_lock:
        result = SOURCE.search(query, "anime")
        if not result:
            return False, f"aucun générique trouvé sur AnimeThemes pour « {query} »"
        _backup_existing(folder)
        if not SOURCE.download(result.url, folder / THEME_FILENAME):
            return False, "téléchargement ou conversion impossible (voir le Journal)"
    emby = EMBY.refresh_series(series.name, title, number)
    return True, f"{result.title} · {emby['message']}"

def _run_normalize():
    """Ramène à TARGET_DB tous les theme.mp3 déjà présents (originaux copiés dans data/themes-backup/)."""
    from src.audio import normalize_file
    files = []
    skipped_other = 0
    for series in library.iter_series_folders(ROOTS):
        for label, folder in [("série", series)] + [(f"saison {n}", f) for n, f in library.season_folders(series)]:
            theme = find_theme(folder)
            if theme is None:
                continue
            if theme.suffix.lower() == ".mp3" and theme.parent == folder:
                files.append((f"{library.clean_title(series.name)} — {label}", theme))
            else:
                skipped_other += 1
    registry = _read_registry()
    backup = BACKUP_DIR / "normalisation" / f"{datetime.now():%Y%m%d-%H%M%S}"
    with _batch_lock:
        BATCH.update(kind="normalize", running=True, stop=False, total=len(files), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(files)} thème(s) MP3 à vérifier (cible {TARGET_DB:g} dB)" + (f" · {skipped_other} autre(s) format(s) ignoré(s)" if skipped_other else ""))
    changed = already = 0
    try:
        for label, path in files:
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
            with _work_lock:
                status, before, after = normalize_file(path, TARGET_DB, backup_dir=backup / _slug(label))
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
            with _batch_lock:
                BATCH["done"] += 1
        try:
            NORMALIZED_FILE.parent.mkdir(parents=True, exist_ok=True)
            NORMALIZED_FILE.write_text(json.dumps(registry))
        except OSError:
            pass
        _batch_note(f"Terminé : {changed} normalisé(s), {already} déjà au bon niveau" + (f" · originaux dans {backup}" if changed else ""))
    except Exception:
        logger.exception("La normalisation s'est arrêtée sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
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
    return jsonify({"items": items, "emby": EMBY.configured, "roots_ok": [Path(r).is_dir() for r in ROOTS]})


@app.route("/api/search", methods=["POST"])
def api_search():
    title = (request.get_json(silent=True) or {}).get("title", "").strip()
    if not title:
        return jsonify({"error": "Titre vide"}), 400
    return jsonify({"results": SOURCE.candidates(title)})


@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.get_json(silent=True) or {}
    folder, series, number = library.resolve_target(ROOTS, data.get("id", ""))
    url = data.get("url", "")
    if not folder:
        return jsonify({"error": "Série ou saison introuvable"}), 404
    if not SOURCE.is_allowed_url(url):
        return jsonify({"error": "Adresse non autorisée (seul animethemes.moe est accepté)"}), 400
    with _work_lock:
        _backup_existing(folder)
        ok = SOURCE.download(url, folder / THEME_FILENAME)
    if not ok:
        return jsonify({"error": "Téléchargement ou conversion impossible (détails : bouton Journal)"}), 502
    emby = EMBY.refresh_series(series.name, data.get("title", ""), number)
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
    ok, msg = _auto_one(folder, title, series, number, query)
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
    with _batch_lock:   # on marque « en cours » tout de suite : la page qui interroge juste après le voit
        if BATCH["running"]:
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        BATCH.update(running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_batch, args=(int(limit) if limit else None, with_seasons), daemon=True).start()
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
diag.init_app(app, APP_VERSION, lambda: ROOTS, EMBY.describe, _batch_state_text)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8001)
