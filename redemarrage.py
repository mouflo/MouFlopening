"""
Alerte « redémarrage inattendu » (même fichier dans MouFlanga, MouFlanimeXer et MouFlopening).

Au démarrage, l'appli pose un témoin « data/en-marche », qu'elle efface à l'arrêt normal (systemd : mise à jour,
redémarrage demandé). Si le témoin est encore là au démarrage suivant, l'appli s'était arrêtée brutalement :
- le serveur a redémarré depuis (coupure de courant, mise à jour du système…) si son heure de démarrage est
  plus récente que le témoin ;
- sinon l'appli a planté (les dernières erreurs du journal sont jointes).
Une appli plantée ne peut pas prévenir au moment même : elle prévient dès que systemd l'a relancée.
Pour couper l'alerte : case dans ⚙️ Réglages (fichier témoin « data/alerte-redemarrage-coupee »).
"""
import atexit
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from flask import jsonify, request

logger = logging.getLogger(__name__)


_DATA = {"dossier": Path(".")}


def active():
    return not (_DATA["dossier"] / "alerte-redemarrage-coupee").exists()


def _erreurs(journal, n=4):
    try:
        lignes = Path(journal).read_text(encoding="utf-8", errors="ignore").splitlines()[-400:]
    except OSError:
        return ""
    err = [l for l in lignes if " ERROR " in l or "Traceback" in l or "Error:" in l]
    return "\n".join(l[-160:] for l in err[-n:])


def verifier(base_dir, nom_appli, journal, envoyer):
    """À appeler une fois, au lancement du vrai service (jamais lors d'un import pour un essai).
    envoyer(texte) envoie un message Telegram avec les réglages de l'appli."""
    data = Path(base_dir) / "data"
    data.mkdir(parents=True, exist_ok=True)
    _DATA["dossier"] = data
    temoin = data / "en-marche"
    if temoin.exists():
        try:
            demarrage_serveur = time.time() - float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            demarrage_serveur = 0
        if demarrage_serveur > temoin.stat().st_mtime:
            texte = f"⚡ {nom_appli} a redémarré : le serveur lui-même a redémarré (coupure de courant, mise à jour du système…)."
        else:
            texte = f"⚠️ {nom_appli} s'était arrêté brutalement (plantage) et vient de redémarrer tout seul."
            e = _erreurs(journal)
            if e:
                texte += "\n\nDernières erreurs du journal :\n" + e
        logger.warning("Arrêt inattendu détecté au démarrage")
        if active():
            def go():
                try:
                    envoyer(texte)
                    logger.info("Alerte de redémarrage envoyée sur Telegram")
                except Exception as ex:
                    logger.warning("Alerte de redémarrage impossible : %s", ex)
            threading.Thread(target=go, daemon=True).start()
    temoin.write_text(str(os.getpid()))

    def propre(*_):
        try:
            temoin.unlink()
        except OSError:
            pass
    atexit.register(propre)

    def sur_sigterm(signum, frame):           # arrêt normal demandé par systemd
        propre()
        sys.exit(0)
    try:
        signal.signal(signal.SIGTERM, sur_sigterm)
    except ValueError:
        pass


def init_app(app, base_dir):
    """Case « Prévenir si l'appli a planté ou si le serveur a redémarré » de la page Réglages."""
    _DATA["dossier"] = Path(base_dir) / "data"

    @app.route("/api/settings/alerte-redemarrage", methods=["GET", "POST"])
    def alerte_redemarrage():
        if request.method == "POST":
            actif = bool((request.get_json(silent=True) or {}).get("actif"))
            coupee = _DATA["dossier"] / "alerte-redemarrage-coupee"
            if actif:
                coupee.unlink(missing_ok=True)
            else:
                coupee.parent.mkdir(parents=True, exist_ok=True)
                coupee.write_text("1")
            return jsonify({"ok": True, "message": "Alerte de redémarrage activée." if actif else "Alerte de redémarrage coupée."})
        return jsonify({"actif": active()})
