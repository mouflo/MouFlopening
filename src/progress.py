"""
Suivi en direct des opérations longues (recherche, téléchargement) :
une opération tourne dans un fil à part, annonce ses étapes avec say(), et la page les affiche au fur et à mesure.
"""
import threading
import time
import uuid

class Cancelled(BaseException):
    """Opération arrêtée à la demande de l'utilisateur (BaseException : les « except Exception » ne l'avalent pas)."""


_local = threading.local()
_jobs = {}
_lock = threading.Lock()


def say(text):
    """Annonce l'étape en cours (sans effet si personne n'écoute)."""
    job = getattr(_local, "job", None)
    if job is not None:
        if job.get("cancel"):
            raise Cancelled()
        with _lock:
            job["steps"].append({"t": round(time.time() - job["t0"], 1), "text": str(text)})


def start(work):
    """Lance work() en arrière-plan ; retourne l'identifiant à interroger."""
    jid = uuid.uuid4().hex[:12]
    job = {"steps": [], "done": False, "result": None, "t0": time.time()}
    with _lock:
        for k in [k for k, v in _jobs.items() if v["done"] and time.time() - v["t0"] > 600]:
            del _jobs[k]
        _jobs[jid] = job

    def run():
        _local.job = job
        try:
            res = work()
        except Cancelled:
            res = ({"cancelled": True}, 200)
        except Exception as e:      # l'erreur est rendue à la page, avec le détail dans le journal
            import logging
            logging.getLogger(__name__).exception("Opération en arrière-plan en erreur")
            res = ({"error": f"Erreur interne : {type(e).__name__}: {e} (détails dans le Journal)"}, 500)
        with _lock:
            job["result"], job["done"] = res, True
    threading.Thread(target=run, daemon=True).start()
    return jid


def status(jid, since=0):
    with _lock:
        job = _jobs.get(jid)
        if not job:
            return None
        return {"steps": job["steps"][since:], "next": len(job["steps"]), "done": job["done"],
                "result": job["result"], "elapsed": round(time.time() - job["t0"], 1)}


def cancel(jid):
    """Demande l'arrêt : l'opération s'arrête à sa prochaine étape annoncée."""
    with _lock:
        job = _jobs.get(jid)
        if job:
            job["cancel"] = True
        return job is not None
