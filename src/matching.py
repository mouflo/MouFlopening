"""Comparaison de titres (sans dépendance externe : difflib est fourni avec Python)."""

import re
from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(sorted(words))          # l'ordre des mots ne compte pas


def similarity(a: str, b: str) -> int:
    """Score de 0 à 100 entre deux titres."""
    return round(SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() * 100)


_MARQUES_SAISON = re.compile(r"^(?:(?:season|saison|part|partie|cour|s)\s*\d+|\d+(?:st|nd|rd|th)?\s*(?:season|saison|part|cour)?|"
                             r"[ivx]+|second|third|fourth|final|the final|2nd|3rd|\d{4})$")


def saison_compatible(serie: str, trouve: str) -> bool:
    """« Dragon Ball » saison 2 → « Dragon Ball Super » : NON (c'est une autre série). « Dragon Ball 2nd Season »,
    « … Season 2 », « … II », « … Part 2 », « … 2014 » : oui. Le nom trouvé doit être la série, plus seulement une marque de saison."""
    simple = lambda t: " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split())    # sans trier les mots (l'ordre compte ici)
    a, b = simple(serie), simple(trouve)
    if not b.startswith(a):
        return similarity(serie, trouve) >= 95
    reste = b[len(a):].strip(" :-")
    return reste == "" or bool(_MARQUES_SAISON.match(reste))
