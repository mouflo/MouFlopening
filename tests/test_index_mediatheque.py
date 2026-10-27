"""🗂 Index SQLite de la médiathèque : même liste que library.list_library, mais seuls les titres changés sont relus."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import library, mediatheque_index as idx  # noqa: E402


class IndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self.tmp.name) / "Series"
        for nom, saisons in (("Alpha (2020)", ["Season 1", "Season 2"]), ("Beta", []), ("Gamma [tvdbid-1]", ["Season 1"])):
            for s in saisons or [None]:
                d = self.racine / nom / s if s else self.racine / nom
                d.mkdir(parents=True)
                (d / "episode.mkv").write_bytes(b"x")
        (self.racine / "Vide").mkdir()                                    # un reste de renommage : pas un titre
        (self.racine / "@eaDir").mkdir()
        (self.racine / "Beta" / "theme.mp3").write_bytes(b"m" * (library.MIN_THEME_BYTES + 10))
        self.roots = [str(self.racine)]
        idx.configurer(Path(self.tmp.name) / "index.sqlite")

    def tearDown(self):
        idx.configurer(None)
        self.tmp.cleanup()

    def _theme(self, dossier):
        (dossier / "theme.mp3").write_bytes(b"m" * (library.MIN_THEME_BYTES + 10))

    def test_meme_liste_que_l_ancienne_methode_a_chaque_fois(self):
        ref = library.list_library(self.roots)
        self.assertEqual(idx.lister(self.roots), ref)                     # index vide
        self.assertEqual(idx.lister(self.roots), ref)                     # index rempli
        self.assertEqual(len(ref), 3)
        self.assertEqual([i["title"] for i in ref], ["Alpha", "Beta", "Gamma"])

    def test_un_titre_inchange_n_est_pas_relu(self):
        idx.lister(self.roots)
        with mock.patch.object(idx, "_calculer", wraps=idx._calculer) as calc:
            idx.lister(self.roots)
        calc.assert_not_called()

    def test_un_theme_pose_dans_un_titre_est_vu(self):
        self.assertFalse(next(i for i in idx.lister(self.roots) if i["name"] == "Alpha (2020)")["has_theme"])
        time.sleep(0.02)
        self._theme(self.racine / "Alpha (2020)")
        self.assertTrue(next(i for i in idx.lister(self.roots) if i["name"] == "Alpha (2020)")["has_theme"])

    def test_un_theme_pose_dans_une_saison_est_vu(self):
        """La date du dossier du titre ne change pas quand un thème arrive dans une saison : la saison est regardée aussi."""
        idx.lister(self.roots)
        time.sleep(0.02)
        self._theme(self.racine / "Alpha (2020)" / "Season 2")
        alpha = next(i for i in idx.lister(self.roots) if i["name"] == "Alpha (2020)")
        self.assertEqual([s["has_theme"] for s in alpha["seasons"]], [False, True])

    def test_titre_efface_ou_ajoute(self):
        idx.lister(self.roots)
        shutil.rmtree(self.racine / "Beta")
        (self.racine / "Delta").mkdir()
        (self.racine / "Delta" / "e.mkv").write_bytes(b"x")
        noms = [i["name"] for i in idx.lister(self.roots)]
        self.assertEqual(noms, ["Alpha (2020)", "Delta", "Gamma [tvdbid-1]"])
        self.assertEqual(idx.lister(self.roots), library.list_library(self.roots))

    def test_partage_absent_ne_vide_pas_l_index(self):
        idx.lister(self.roots)
        autre = Path(self.tmp.name) / "Films"                               # une 2e racine, absente pour l'instant
        self.assertEqual(len(idx.lister(self.roots + [str(autre)])), 3)
        shutil.move(str(self.racine), str(self.racine) + "_demonte")        # le NAS disparaît un instant
        self.assertEqual(idx.lister(self.roots), [])
        shutil.move(str(self.racine) + "_demonte", str(self.racine))
        with mock.patch.object(idx, "_calculer", wraps=idx._calculer) as calc:
            self.assertEqual(len(idx.lister(self.roots)), 3)
        calc.assert_not_called()                                           # tout était resté dans l'index

    def test_controle_complet_recalcule_tout(self):
        idx.lister(self.roots)
        with mock.patch.object(idx, "_calculer", wraps=idx._calculer) as calc:
            idx.lister(self.roots, tout=True)
        self.assertEqual(calc.call_count, 4)                               # les 3 titres + le dossier vide

    def test_fichier_sqlite_abime_retour_a_la_methode_d_avant(self):
        Path(self.tmp.name, "index.sqlite").write_bytes(b"pas du sqlite" * 50)
        self.assertEqual(idx.lister(self.roots), library.list_library(self.roots))

    def test_sans_index_configure_methode_d_avant(self):
        idx.configurer(None)
        self.assertEqual(idx.lister(self.roots), library.list_library(self.roots))

    def test_les_dicts_rendus_peuvent_etre_modifies_sans_toucher_l_index(self):
        a = idx.lister(self.roots)
        a[0]["skipped"] = True
        a[0]["seasons"].clear()
        self.assertNotIn("skipped", idx.lister(self.roots)[0])
        self.assertEqual(len(idx.lister(self.roots)[0]["seasons"]), 2)


if __name__ == "__main__":
    unittest.main()
