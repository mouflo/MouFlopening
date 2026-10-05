#!/usr/bin/env python3
"""
MouFlopening - interface web (même conception que MouFloster et MouFlanimeXer).

- Liste de la médiathèque : séries avec ou sans thème
- Choix manuel : on écoute les génériques proposés par AnimeThemes puis on clique « Utiliser »
- Mode automatique : une série, ou toutes celles qui n'ont pas de thème (avec barre de progression)
- Le thème est enregistré sous theme.mp3 dans le dossier de la série, puis Emby actualise cette série seule
"""

import logging
import subprocess
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from src.config import load_config, load_secrets_env

BASE_DIR = Path(__file__).resolve().parent
load_secrets_env()   # identifiants et clé Emby (data/secrets.env), avant l'initialisation de la connexion

from src import library
from src.emby_client import EmbyClient
from src.library import THEME_FILENAME
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
SOURCE = AnimeThemesSource(CONFIG.get("sources", {}).get("animethemes", {"enabled": True}),
                           threshold=CONFIG.get("matching", {}).get("threshold", 70))

app = Flask(__name__)

import auth
import diag

diag.setup_logging()
logger = logging.getLogger("mouflopening")
auth.init_app(app, APP_VERSION)

_work_lock = threading.Lock()   # un seul téléchargement/conversion à la fois (ménage le NAS et le CPU)

# ---------------------------------------------------------------------------
# Téléchargement automatique de toutes les séries sans thème (en arrière-plan)
# ---------------------------------------------------------------------------

BATCH = {"running": False, "stop": False, "total": 0, "done": 0, "failed": 0, "current": "", "messages": []}
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


def _run_batch(limit):
    todo = library.missing_themes(ROOTS)
    if limit:
        todo = todo[:limit]
    with _batch_lock:
        BATCH.update(running=True, stop=False, total=len(todo), done=0, failed=0, current="", messages=[])
    _batch_note(f"{len(todo)} série(s) à traiter")
    try:
        for title, folder in todo:
            if BATCH["stop"]:
                _batch_note("Arrêt demandé")
                break
            with _batch_lock:
                BATCH["current"] = title
            ok, msg = _auto_one(folder, title)
            with _batch_lock:
                BATCH["done" if ok else "failed"] += 1
            _batch_note(("✅ " if ok else "❌ ") + f"{title} — {msg}")
    except Exception:
        logger.exception("Le lot s'est arrêté sur une erreur")
        _batch_note("⚠️ Erreur inattendue (détails dans le Journal)")
    finally:
        with _batch_lock:
            BATCH.update(running=False, current="")


def _auto_one(folder, title):
    """Choisit automatiquement le meilleur générique, l'enregistre et prévient Emby. -> (succès, message)"""
    with _work_lock:
        result = SOURCE.search(title, "anime")
        if not result:
            return False, "aucun générique trouvé sur AnimeThemes"
        if not SOURCE.download(result.url, folder / THEME_FILENAME):
            return False, "téléchargement ou conversion impossible (voir le Journal)"
    emby = EMBY.refresh_series(folder.name, title)
    return True, f"{result.title} · {emby['message']}"

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.route("/")
def index():
    return render_template("index.html", version=APP_VERSION)


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
    folder = library.resolve_folder(ROOTS, data.get("id", ""))
    url = data.get("url", "")
    if not folder:
        return jsonify({"error": "Série introuvable"}), 404
    if not SOURCE.is_allowed_url(url):
        return jsonify({"error": "Adresse non autorisée (seul animethemes.moe est accepté)"}), 400
    with _work_lock:
        ok = SOURCE.download(url, folder / THEME_FILENAME)
    if not ok:
        return jsonify({"error": "Téléchargement ou conversion impossible (détails : bouton Journal)"}), 502
    emby = EMBY.refresh_series(folder.name, data.get("title", ""))
    logger.info("Thème enregistré : %s", folder / THEME_FILENAME)
    return jsonify({"ok": True, "message": f"Thème enregistré. {emby['message']}", "emby_ok": emby["ok"]})


@app.route("/api/auto", methods=["POST"])
def api_auto():
    data = request.get_json(silent=True) or {}
    folder = library.resolve_folder(ROOTS, data.get("id", ""))
    if not folder:
        return jsonify({"error": "Série introuvable"}), 404
    title = (data.get("title") or library.clean_title(folder.name)).strip()
    ok, msg = _auto_one(folder, title)
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 404)


@app.route("/api/theme")
def api_theme():
    folder = library.resolve_folder(ROOTS, request.args.get("id", ""))
    path = folder / THEME_FILENAME if folder else None
    if not path or not path.is_file():
        return jsonify({"error": "Pas de thème"}), 404
    return send_file(path, mimetype="audio/mpeg", conditional=True)


@app.route("/api/batch/start", methods=["POST"])
def api_batch_start():
    limit = (request.get_json(silent=True) or {}).get("limit")
    with _batch_lock:   # on marque « en cours » tout de suite : la page qui interroge juste après le voit
        if BATCH["running"]:
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        BATCH.update(running=True, stop=False, total=0, done=0, failed=0, current="Préparation…", messages=[])
    threading.Thread(target=_run_batch, args=(int(limit) if limit else None,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/batch/stop", methods=["POST"])
def api_batch_stop():
    BATCH["stop"] = True
    return jsonify({"ok": True})


@app.route("/api/batch/status")
def api_batch_status():
    with _batch_lock:
        return jsonify(dict(BATCH))


diag.init_app(app, APP_VERSION, lambda: ROOTS, EMBY.describe, _batch_state_text)

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8001)
