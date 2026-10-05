"""
Contournement d'un bug de compatibilité : yt-dlp remplace une pièce interne de urllib3 (_PERCENT_RE)
par un objet incomplet. Après ça, TOUTES les requêtes faites avec « requests » (TheMovieDB, ThemerrDB…)
plantent avec « 'Urllib3PercentREOverride' object has no attribute 'sub' ».
On remet la pièce d'origine avant chaque requête : sans effet si tout est normal.
"""
import re


def repair_urllib3():
    try:
        import urllib3.util.url as u
    except Exception:
        return
    for name in ("_PERCENT_RE", "PERCENT_RE"):
        obj = getattr(u, name, None)
        if obj is None or hasattr(type(obj), "sub") or isinstance(obj, re.Pattern):
            continue
        orig = None
        try:
            orig = object.__getattribute__(obj, "re")
        except Exception:
            pass
        if not isinstance(orig, re.Pattern):
            orig = re.compile(r"%[a-fA-F0-9]{2}")
        setattr(u, name, orig)
