"""Saison d'un anime : la fiche AnimeThemes trouvée doit être la même série (cas Dragon Ball → Dragon Ball Super)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.matching import saison_compatible  # noqa: E402


class SaisonTest(unittest.TestCase):
    def test_autre_serie_refusee(self):
        self.assertFalse(saison_compatible("Dragon Ball", "Dragon Ball Super"))
        self.assertFalse(saison_compatible("Dragon Ball", "Dragon Ball Z"))

    def test_marques_de_saison(self):
        for nom in ("Dragon Ball", "Dragon Ball 2nd Season", "Dragon Ball Season 2", "Dragon Ball II", "Dragon Ball: Part 2", "Dragon Ball (2014)"):
            self.assertTrue(saison_compatible("Dragon Ball", nom), nom)


if __name__ == "__main__":
    unittest.main()
