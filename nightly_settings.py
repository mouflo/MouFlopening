"""
Réglages du lot de nuit et de Telegram depuis la page web.
Le jeton du bot est enregistré dans data/secrets.env (jamais sur GitHub) et n'est jamais renvoyé à la page.
"""
import logging
import os
from pathlib import Path

from flask import jsonify, request

from emby_settings import _write_secret

logger = logging.getLogger(__name__)


def init_app(app, base_dir, nightly, run_now, is_busy):
    secrets_file = Path(base_dir) / "data" / "secrets.env"

    @app.route("/api/nightly")
    def nightly_state():
        tok, chat, origin = nightly.telegram_config()
        s = nightly.settings()
        return jsonify({**s, "telegram": bool(tok and chat), "telegram_origin": origin,
                        "chat_hint": ("…" + chat[-3:]) if chat else ""})

    @app.route("/api/nightly", methods=["POST"])
    def nightly_save():
        body = request.get_json(silent=True) or {}
        try:
            hour = int(body.get("hour", 3))
        except (TypeError, ValueError):
            return jsonify({"error": "Heure invalide"}), 400
        if not 0 <= hour <= 23:
            return jsonify({"error": "Heure invalide (0 à 23)"}), 400
        nightly.save(enabled=bool(body.get("enabled")), hour=hour)
        logger.info("Lot de nuit : %s à %d h", "activé" if body.get("enabled") else "désactivé", hour)
        return jsonify({"ok": True})

    @app.route("/api/nightly/run", methods=["POST"])
    def nightly_run():
        if is_busy():
            return jsonify({"error": "Un lot est déjà en cours"}), 409
        run_now()
        return jsonify({"ok": True})

    @app.route("/api/settings/telegram", methods=["POST"])
    def telegram_save():
        body = request.get_json(silent=True) or {}
        tok, chat = str(body.get("token", "")).strip(), str(body.get("chat_id", "")).strip()
        if not tok and not chat:                      # seulement tester ce qui est déjà réglé
            ok, msg = nightly.send("✅ MouFlopening : Telegram fonctionne, tu recevras ici le compte rendu de la nuit 🌙")
            return jsonify({"ok": ok, "message": msg})
        cur_tok, cur_chat, _o = nightly.telegram_config()
        tok, chat = tok or cur_tok, chat or cur_chat
        if not nightly.valid_token(tok):
            return jsonify({"ok": False, "error": "Jeton invalide : il ressemble à 123456789:ABC… (donné par @BotFather), sans espace."}), 400
        if not nightly.valid_chat(chat):
            return jsonify({"ok": False, "error": "Identifiant de discussion invalide : un nombre (ex. 123456789), ou @nom d'un canal."}), 400
        ok, msg = nightly.check_bot(tok)
        if not ok:
            return jsonify({"ok": False, "error": msg + ". Rien n'a été enregistré."}), 400
        ok, msg = nightly.send("✅ MouFlopening : Telegram fonctionne, tu recevras ici le compte rendu de la nuit 🌙", tok, chat)
        if not ok:
            return jsonify({"ok": False, "error": msg + ". Rien n'a été enregistré (as-tu écrit un message à ton bot au moins une fois ?)."}), 400
        _write_secret(secrets_file, "TELEGRAM_BOT_TOKEN", tok)
        _write_secret(secrets_file, "TELEGRAM_CHAT_ID", chat)
        os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"] = tok, chat
        logger.info("Telegram réglé depuis la page web")
        return jsonify({"ok": True, "message": "Enregistré : un message de test vient d'arriver sur Telegram."})
