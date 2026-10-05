"""
Journal et diagnostic intégrés à l'appli : une fenêtre « Journal » affiche un rapport complet
(état du serveur, réglages, dernières lignes du journal) à copier-coller directement,
sans se connecter au serveur. Les clés et mots de passe sont masqués automatiquement.
"""

import logging
import logging.handlers
import platform
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from flask import jsonify, request

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE = DATA_DIR / "mouflopening.log"

logger = logging.getLogger("mouflopening.diag")

_SECRET_PATTERNS = [
    (re.compile(r"(api_key=)[^&\s\"']+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.I), r"\1***"),
    (re.compile(r"(X-Emby-Token['\":= ]+)[A-Za-z0-9]+", re.I), r"\1***"),
    (re.compile(r"(EMBY_API_KEY=)\S+"), r"\1***"),
    (re.compile(r"(APP_PASSWORD_HASH=)\S+"), r"\1***"),
    (re.compile(r"(\b(?:password|passwd|mot_de_passe)=)[^&\s]+", re.I), r"\1***"),
]


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def setup_logging():
    """Journal dans la console ET dans data/mouflopening.log (tourne tout seul : 1 Mo x 3 fichiers)"""
    fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in list(root.handlers):
        root.removeHandler(h)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError as e:
        root.warning(f"Journal fichier indisponible : {e}")
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def _tail(path: Path, lines: int, max_bytes: int = 200_000) -> str:
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            data = f.read().decode("utf-8", errors="replace")
        return "\n".join(data.splitlines()[-lines:])
    except OSError:
        return "(aucun journal pour le moment)"


def _mem():
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, v = line.split(":", 1)
            info[k] = int(v.split()[0])
        return f"{info['MemAvailable'] // 1024} Mo libres sur {info['MemTotal'] // 1024} Mo"
    except Exception:
        return "inconnue"


def _disk(path):
    try:
        u = shutil.disk_usage(path)
        return f"{u.free / 1e9:.1f} Go libres sur {u.total / 1e9:.0f} Go"
    except OSError as e:
        return f"inaccessible ({e})"


def build_report(version, roots, emby_state, batch_state):
    lines = [
        f"=== Rapport MouFlopening · {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} ===",
        f"Version : {version}",
        f"Python  : {sys.version.split()[0]} · {platform.platform()}",
        f"Mémoire : {_mem()}",
        f"Disque  : appli {_disk(BASE_DIR)}",
        f"ffmpeg  : {'présent' if shutil.which('ffmpeg') else 'ABSENT (apt install ffmpeg)'}",
        "",
        "--- Réglages ---",
        f"Emby : {emby_state}",
    ]
    for r in roots:
        p = Path(r)
        lines.append(f"Médiathèque : {r} → " + ("accessible" if p.is_dir() else "INTROUVABLE")
                     + (f" · écriture {'OK' if p.is_dir() and __import__('os').access(r, 1 << 1) else 'IMPOSSIBLE'}" if p.is_dir() else ""))
    lines += ["", "--- Téléchargement automatique ---", batch_state, "",
              "--- Journal de l'appli (150 dernières lignes) ---", _tail(LOG_FILE, 150)]
    return redact("\n".join(lines))


def init_app(app, version, roots_fn, emby_state_fn, batch_state_fn):
    logger.info(f"Démarrage MouFlopening {version} · Python {sys.version.split()[0]}")

    @app.route("/api/diagnostic")
    def api_diagnostic():
        return jsonify({"report": build_report(version, roots_fn(), emby_state_fn(), batch_state_fn())})

    @app.route("/api/clientlog", methods=["POST"])
    def api_clientlog():
        data = request.get_json(silent=True) or {}
        logger.error(f"[navigateur] {str(data.get('message', ''))[:400]} ({str(data.get('where', ''))[:200]})")
        return jsonify({"ok": True})

    @app.errorhandler(Exception)
    def on_error(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc
        logger.exception(f"Erreur non gérée sur {request.method} {request.path}")
        if request.path.startswith("/api/"):
            return jsonify({"error": f"Erreur interne : {type(exc).__name__}: {exc} (détails dans le Journal)"}), 500
        raise exc
