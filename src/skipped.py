"""
Titres « mis de côté » : recherchés sans résultat (ou écartés à la main). Ils quittent la liste « sans thème »
pour qu'on ne retombe pas dessus à chaque fois ; ils restent consultables dans le filtre « Recherché sans résultat ».
Enregistré dans data/skipped.json (chemins des dossiers).
"""
import json
import threading
from pathlib import Path

_lock = threading.Lock()
_file = None


def init(path):
    global _file
    _file = Path(path)


def _read():
    try:
        return set(json.loads(_file.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return set()


def _write(s):
    try:
        _file.parent.mkdir(parents=True, exist_ok=True)
        tmp = _file.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(s), ensure_ascii=False, indent=0), encoding="utf-8")
        tmp.replace(_file)
    except OSError:
        pass


def all_keys():
    with _lock:
        return _read()


def add(folder):
    with _lock:
        s = _read(); s.add(str(folder)); _write(s)


def remove(folder):
    with _lock:
        s = _read()
        if str(folder) in s:
            s.discard(str(folder)); _write(s)
