"""
Titres « mis de côté » : recherchés sans résultat (ou écartés à la main). Ils quittent la liste « sans thème »
pour qu'on ne retombe pas dessus à chaque fois ; ils restent consultables dans le filtre « Recherché sans résultat ».
Enregistré dans data/skipped.json : {chemin du dossier: {"reason": "...", "date": "AAAA-MM-JJ"}}
(l'ancien format, une simple liste de chemins, est relu et converti).
Les lots peuvent ignorer les entrées trop anciennes (réglage « réessayer après N jours ») pour retenter ces titres.
"""
import json
import threading
from datetime import date, timedelta
from pathlib import Path

_lock = threading.Lock()
_file = None


def init(path):
    global _file
    _file = Path(path)


def _read():
    try:
        data = json.loads(_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if isinstance(data, list):                      # ancien format : date inconnue -> aujourd'hui (on repart de là)
        today = date.today().isoformat()
        return {str(k): {"reason": "", "date": today} for k in data}
    if isinstance(data, dict):
        return {str(k): (v if isinstance(v, dict) else {"reason": "", "date": date.today().isoformat()}) for k, v in data.items()}
    return {}


def _write(d):
    try:
        _file.parent.mkdir(parents=True, exist_ok=True)
        tmp = _file.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
        tmp.replace(_file)
    except OSError:
        pass


def all_keys(max_age_days=None):
    """Chemins mis de côté. max_age_days : seulement ceux mis de côté il y a moins de N jours (0 ou None = tous)."""
    with _lock:
        d = _read()
    if not max_age_days:
        return set(d)
    limit = (date.today() - timedelta(days=int(max_age_days))).isoformat()
    return {k for k, v in d.items() if (v.get("date") or "9999") > limit}


def entries():
    with _lock:
        return _read()


def add(folder, reason=""):
    with _lock:
        d = _read()
        d[str(folder)] = {"reason": str(reason or "")[:200], "date": date.today().isoformat()}
        _write(d)


def remove(folder):
    with _lock:
        d = _read()
        if str(folder) in d:
            d.pop(str(folder))
            _write(d)


def clear_under(roots):
    """Réessayer : retire les titres mis de côté situés dans ces dossiers (un onglet). -> nombre retiré."""
    prefixes = [str(Path(r)).rstrip("/") + "/" for r in roots]
    with _lock:
        d = _read()
        keep = {k: v for k, v in d.items() if not any((k + "/").startswith(p) for p in prefixes)}
        n = len(d) - len(keep)
        if n:
            _write(keep)
    return n
