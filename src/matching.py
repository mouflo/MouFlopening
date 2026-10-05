"""Comparaison de titres (sans dépendance externe : difflib est fourni avec Python)."""

import re
from difflib import SequenceMatcher


def _normalize(text: str) -> str:
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(sorted(words))          # l'ordre des mots ne compte pas


def similarity(a: str, b: str) -> int:
    """Score de 0 à 100 entre deux titres."""
    return round(SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() * 100)
