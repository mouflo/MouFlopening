"""📁 Onglets Animes / Séries / Films : recalculés quand le NAS apparaît après le démarrage, jamais vidés par un partage qui disparaît."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import library  # noqa: E402


class OngletsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.parent = Path(self.tmp.name) / "Emby-Media"
        self.cfg = {"library": {"auto_parent": str(self.parent), "paths": [str(self.parent / "Manga")]}}
        self.cats, self.roots, self.root_cat, self.ign = [], [], [], []

    def tearDown(self):
        self.tmp.cleanup()

    def _recalcul(self):
        return library.recalculer_onglets(self.cfg, self.cats, self.roots, self.root_cat, self.ign)

    def test_nas_monte_en_retard_les_onglets_reviennent(self):
        # au démarrage le partage n'est pas encore monté : seul l'ancien chemin de config.json, introuvable
        self.cats[:] = library.discover_categories(self.cfg, self.ign)
        self.assertEqual([c["kind"] for c in self.cats], ["anime"])
        self.assertFalse(self.cats[0]["ok"])
        # le partage apparaît
        for nom in ("Manga", "Series", "Films HD", "Films 4k"):
            (self.parent / nom).mkdir(parents=True)
        self.assertTrue(self._recalcul())
        self.assertEqual([c["kind"] for c in self.cats], ["anime", "series", "movie"])
        self.assertTrue(all(c["ok"] for c in self.cats))
        self.assertEqual(len(self.cats[2]["paths"]), 2)                       # Films HD + Films 4k regroupés
        self.assertEqual(len(self.roots), 4)
        self.assertEqual(self.root_cat, [0, 1, 2, 2])
        self.assertFalse(self._recalcul())                                    # plus rien à changer

    def test_les_listes_gardees_ailleurs_sont_modifiees_sur_place(self):
        autre_reference = self.roots                                          # copain_themes garde la liste ROOTS elle-même
        (self.parent / "Series").mkdir(parents=True)
        self._recalcul()
        self.assertIs(autre_reference, self.roots)
        self.assertEqual(len(autre_reference), 2)                             # Series + l'ancien chemin « Manga » de config.json

    def test_partage_qui_disparait_ne_vide_pas_les_onglets(self):
        for nom in ("Manga", "Series"):
            (self.parent / nom).mkdir(parents=True)
        self._recalcul()
        self.assertEqual(len(self.cats), 2)
        shutil.rmtree(self.parent)                                            # NAS démonté un instant
        self.assertFalse(self._recalcul())
        self.assertEqual(len(self.cats), 2)
        self.assertEqual(len(self.roots), 2)

    def test_un_nouveau_dossier_s_ajoute(self):
        (self.parent / "Series").mkdir(parents=True)
        self._recalcul()
        (self.parent / "Films HD").mkdir()
        self.assertTrue(self._recalcul())
        self.assertEqual([c["kind"] for c in self.cats], ["anime", "series", "movie"])


if __name__ == "__main__":
    unittest.main()
