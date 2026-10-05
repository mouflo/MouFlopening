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
from src import library, ytcookies

logger = logging.getLogger(__name__)
_URL_RE = re.compile(r"^https?://[^\s/]+(:\d{1,5})?(/\S*)?$")
_BAD_CHARS = set('"$`\\\n\r')     # interdits : ils casseraient le fichier data/secrets.env


def init_app(app, base_dir, version_fn, get_config, get_cats, get_ignored, emby, backup_default, get_db=None, set_db=None):
    base_dir = Path(base_dir)
    import fs_browser
    fs_browser.init_app(app)

    @app.route("/reglages")
    def settings_page():
        return render_template("reglages.html", version=version_fn())

    def _folders(cfg):
        """Les dossiers de médiathèque proposés : sous-dossiers du dossier parent (cochés ou non) + dossiers ajoutés à la main."""
        lib = cfg.get("library", {})
        excluded, kinds = set(lib.get("excluded") or []), dict(lib.get("kinds") or {})
        out = []
        for sub in library.auto_subfolders(lib.get("auto_parent")):
            kind = kinds.get(str(sub)) or library.guess_kind(sub.name) or ""
            out.append({"path": str(sub), "name": sub.name, "kind": kind, "guess": library.guess_kind(sub.name) or "",
                        "enabled": bool(kind) and str(sub) not in excluded, "auto": True})
        for c in lib.get("categories", []) or []:
            if isinstance(c, dict):
                for path in ([c["path"]] if c.get("path") else []) + list(c.get("paths") or []):
                    out.append({"path": path, "name": Path(path).name or path, "kind": c.get("kind") or library.guess_kind(c.get("name") or Path(path).name) or "series",
                                "guess": "", "enabled": True, "auto": False, "label": c.get("name") or ""})
        return out

    @app.route("/api/settings/paths")
    def paths_state():
        cfg = get_config(); lib = cfg.get("library", {})
        return jsonify({
            "emby_host": emby.host,
            "auto_parent": lib.get("auto_parent", ""),
            "backup_dir": (cfg.get("themes", {}) or {}).get("backup_dir") or backup_default,
            "folders": _folders(cfg),
            "tabs": [{"name": c["name"], "kind": c["kind"], "paths": c["paths"], "ok": c["ok"]} for c in get_cats()],
            "ignored": list(get_ignored()),
        })

    @app.route("/api/settings/emby-host", methods=["POST"])
    def emby_host_save():
        host = str((request.get_json(silent=True) or {}).get("host", "")).strip().rstrip("/")
        if not _URL_RE.match(host) or _BAD_CHARS & set(host):
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
        folders = body.get("folders") or []
        if parent and not Path(parent).is_dir():
            return jsonify({"ok": False, "error": f"Dossier introuvable sur le serveur : « {parent} ». Rien n'a été enregistré."}), 400
        if backup and not (Path(backup).is_dir() or Path(backup).parent.is_dir()):
            return jsonify({"ok": False, "error": f"Le dossier des anciens thèmes « {backup} » n'est pas accessible (le partage est-il monté ?). Rien n'a été enregistré."}), 400
        excluded, kinds, extras = [], {}, []
        for f in folders:
            if not isinstance(f, dict):
                continue
            path, kind, on = str(f.get("path", "")).strip(), str(f.get("kind", "")), bool(f.get("enabled"))
            if kind not in library.KINDS and not (kind == "" and not on):
                return jsonify({"ok": False, "error": f"Choisis le type (film, série ou anime) du dossier « {path} »."}), 400
            if f.get("auto"):
                if not on:
                    excluded.append(path)
                elif kind != library.guess_kind(Path(path).name):
                    kinds[path] = kind
            elif on:
                if not Path(path).is_dir():
                    return jsonify({"ok": False, "error": f"Dossier introuvable sur le serveur : « {path} »."}), 400
                item = {"kind": kind, "path": path}
                if f.get("label"):
                    item["name"] = str(f["label"])
                extras.append(item)
        path = base_dir / "config.json"
        try:
            cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return jsonify({"ok": False, "error": "config.json est illisible : rien n'a été modifié."}), 500
        lib = cfg.setdefault("library", {})
        lib["auto_parent"] = parent
        lib["excluded"], lib["kinds"], lib["categories"] = excluded, kinds, extras
        if backup:
            cfg.setdefault("themes", {})["backup_dir"] = backup
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        logger.info("Dossiers mis à jour depuis la page web : parent %s · %d décoché(s) · %d ajouté(s) · sauvegardes : %s", parent, len(excluded), len(extras), backup or "(inchangé)")
        if body.get("restart", True):                          # le service redémarre tout seul (systemd) et relit les dossiers
            threading.Thread(target=lambda: (time.sleep(1.5), os._exit(0)), daemon=True).start()
        return jsonify({"ok": True, "restart": bool(body.get("restart", True)), "message": "Enregistré. L'appli redémarre pour relire les dossiers…"})

    @app.route("/api/settings/audio")
    def audio_state():
        return jsonify({"target_db": get_db() if get_db else 89})

    @app.route("/api/settings/audio", methods=["POST"])
    def audio_save():
        try:
            value = round(float(str((request.get_json(silent=True) or {}).get("target_db", "")).replace(",", ".")), 1)
        except ValueError:
            return jsonify({"ok": False, "error": "Entre un nombre, par exemple 89."}), 400
        if not 70 <= value <= 100:
            return jsonify({"ok": False, "error": "Choisis un niveau entre 70 et 100 dB (89 est la référence habituelle)."}), 400
        path = base_dir / "config.json"
        try:
            cfg = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except ValueError:
            return jsonify({"ok": False, "error": "config.json est illisible : rien n'a été modifié."}), 500
        cfg.setdefault("audio", {})["target_db"] = value
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
        if set_db:
            set_db(value)                               # pris en compte tout de suite, sans redémarrer
        logger.info("Niveau des thèmes réglé à %g dB depuis la page web", value)
        return jsonify({"ok": True, "message": f"Enregistré : les prochains thèmes seront à {value:g} dB. Les thèmes déjà en place ne changent pas : utilise « Normaliser les thèmes existants » sur la page d'accueil pour les ramener à ce niveau."})

    @app.route("/api/settings/youtube-cookies")
    def yt_cookies_state():
        return jsonify(ytcookies.state())

    @app.route("/api/settings/youtube-cookies", methods=["POST"])
    def yt_cookies_save():
        body = request.get_json(silent=True) or {}
        if body.get("clear"):
            ytcookies.clear()
            logger.info("Cookies YouTube supprimés")
            return jsonify({"ok": True, "message": "Cookies supprimés."})
        text = str(body.get("text", ""))
        ok, msg, _n = ytcookies.validate(text)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 400
        if body.get("test"):
            return jsonify({"ok": True, "message": msg})
        ytcookies.save(text)
        logger.info("Cookies YouTube enregistrés (%s)", msg)
        return jsonify({"ok": True, "message": "Enregistré : " + msg})
