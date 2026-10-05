"""
Page « ⚙️ Réglages » : adresse d'Emby, dossiers de la médiathèque, dossier des anciens thèmes.
(Les clés et Telegram ont leurs routes dans emby_settings.py, tmdb_settings.py et nightly_settings.py.)
- L'adresse d'Emby est enregistrée dans data/secrets.env (EMBY_URL) et prise en compte tout de suite
- Les dossiers sont enregistrés dans config.json (local, jamais sur GitHub) ; l'appli redémarre ensuite toute seule pour les relire
"""
import json
import logging
import os
import re
import threading
import time
from pathlib import Path

from flask import jsonify, render_template, request

from emby_settings import _write_secret

logger = logging.getLogger(__name__)
_URL_RE = re.compile(r"^https?://[^\s/]+(:\d{1,5})?(/\S*)?$")


def init_app(app, base_dir, version_fn, get_config, get_cats, get_ignored, emby, backup_default):
    base_dir = Path(base_dir)

    @app.route("/reglages")
    def settings_page():
        return render_template("reglages.html", version=version_fn())

    @app.route("/api/settings/paths")
    def paths_state():
        lib = get_config().get("library", {})
        return jsonify({
            "emby_host": emby.host,
            "auto_parent": lib.get("auto_parent", ""),
            "backup_dir": (get_config().get("themes", {}) or {}).get("backup_dir") or backup_default,
            "tabs": [{"name": c["name"], "kind": c["kind"], "paths": c["paths"], "ok": c["ok"]} for c in get_cats()],
            "ignored": list(get_ignored()),
        })

    @app.route("/api/settings/emby-host", methods=["POST"])
    def emby_host_save():
        host = str((request.get_json(silent=True) or {}).get("host", "")).strip().rstrip("/")
        if not _URL_RE.match(host):
            return jsonify({"ok": False, "error": "Adresse invalide : elle doit ressembler à http://192.168.1.134:8096"}), 400
        _write_secret(base_dir / "data" / "secrets.env", "EMBY_URL", host)
        os.environ["EMBY_URL"] = host
        emby.host = host
        logger.info("Adresse d'Emby mise à jour depuis la page web : %s", host)
        return jsonify({"ok": True, "message": "Adresse enregistrée."})

    @app.route("/api/settings/paths", methods=["POST"])
    def paths_save():
        body = request.get_json(silent=True) or {}
        parent, backup = str(body.get("auto_parent", "")).strip(), str(body.get("backup_dir", "")).strip()
        if not parent or not Path(parent).is_dir():
            return jsonify({"ok": False, "error": f"Dossier introuvable sur le serveur : « {parent} ». Rien n'a été enregistré."}), 400
        if backup and not (Path(backup).is_dir() or Path(backup).parent.is_dir()):
            return jsonify({"ok": False, "error": f"Le dossier des anciens thèmes « {backup} » n'est pas accessible (le partage est-il monté ?). Rien n'a été enregistré."}), 400
        path = base_dir / "config.json"
        try:
            cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return jsonify({"ok": False, "error": "config.json est illisible : rien n'a été modifié."}), 500
        cfg.setdefault("library", {})["auto_parent"] = parent
        if backup:
            cfg.setdefault("themes", {})["backup_dir"] = backup
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        logger.info("Dossiers mis à jour depuis la page web : %s · sauvegardes : %s", parent, backup or "(inchangé)")
        if body.get("restart", True):                          # le service redémarre tout seul (systemd) et relit les dossiers
            threading.Thread(target=lambda: (time.sleep(1.5), os._exit(0)), daemon=True).start()
        return jsonify({"ok": True, "restart": bool(body.get("restart", True)), "message": "Enregistré. L'appli redémarre pour relire les dossiers…"})
