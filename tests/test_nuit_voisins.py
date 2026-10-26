"""🌙 Lot de nuit et 🔗 MouFloster : titres absents de ThemerrDB retenus 7 jours (pas de recherche inutile chaque nuit),
Telegram ne signale que les nouveaux titres sans thème, arrivées dans Emby (générique et poster), générique cherché à la
demande de MouFloster. Dossiers factices, rien de réel n'est touché, aucun appel réseau."""
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import nightly  # noqa: E402


class RapportTest(unittest.TestCase):
    def test_seulement_les_nouveaux_sans_theme(self):
        lot = [{"kind": "movie", "added": [], "failed": 3, "failures": [
            ("Wicked", "pas de thème validé par la communauté (ThemerrDB : …)", "/m/Films/Wicked"),
            ("Watson", "pas de thème validé par la communauté (ThemerrDB : …)", "/m/Films/Watson"),
            ("Verity", "pas de thème validé par la communauté (ThemerrDB : …)", "/m/Films/Verity")]}]
        t = nightly.format_report(lot, 60, datetime(2026, 10, 27, 3), deja={"/m/Films/Watson", "/m/Films/Verity"})
        self.assertIn("1 titre sans thème validé", t)
        self.assertIn("Wicked", t)
        self.assertNotIn("Watson", t)
        self.assertIn("2 titres toujours sans thème", t)

    def test_rien_de_nouveau_pas_de_message(self):
        lot = [{"kind": "movie", "added": [], "failed": 1, "failures": [("Watson", "ThemerrDB", "/m/Films/Watson")]}]
        self.assertIsNone(nightly.format_report(lot, 60, deja={"/m/Films/Watson"}))

    def test_arrivees_dans_emby(self):
        arr = {"lignes": ["  🎬 Wicked (2024) — 🎵 posé cette nuit · 🖼️ à faire"], "total": 3, "posters": 2, "lien": "https://poster.exemple"}
        t = nightly.format_report([{"kind": "movie", "added": [], "failed": 0, "failures": []}], 60, arrivees=arr)
        self.assertIn("🆕 Arrivés dans Emby : 3", t)
        self.assertIn("Wicked (2024)", t)
        self.assertIn("… et 2 autres", t)
        self.assertIn("2 posters à faire dans MouFloster : https://poster.exemple", t)

    def test_signales_gardes_dans_les_reglages(self):
        with tempfile.TemporaryDirectory() as d:
            nightly.init(Path(d) / "nightly.json")
            nightly.save(signales=["/a", "/b"], dernier_rapport="2026-10-26T02:00:00Z")
            nightly.save(last_run="2026-10-27")                        # une autre sauvegarde ne les efface pas
            s = nightly.settings()
            self.assertEqual((s["signales"], s["dernier_rapport"]), (["/a", "/b"], "2026-10-26T02:00:00Z"))


class AppliBase(unittest.TestCase):
    """L'appli, avec une médiathèque factice (un onglet Films) et des registres dans un dossier temporaire."""

    def setUp(self):
        import app as A
        self.A = A
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.films = base / "Films"
        (self.films / "Wicked (2024)").mkdir(parents=True)
        (self.films / "Dune (2021)").mkdir()
        (self.films / "Dune (2021)" / "theme.mp3").write_bytes(b"x" * 10000)
        self.patches = [mock.patch.object(A, "ROOTS", [str(self.films)]), mock.patch.object(A, "ROOT_CAT", [0]),
                        mock.patch.object(A, "CATS", [{"name": "Films", "kind": "movie", "paths": [str(self.films)], "ok": True}]),
                        mock.patch.object(A, "ABSENTS_FILE", base / "absents.json"),
                        mock.patch.object(A.EMBY, "refresh_series", lambda *a, **k: {"ok": True, "message": "Emby actualise"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()


class AbsentsTest(AppliBase):
    def test_absent_retenu_sans_nouvelle_recherche(self):
        dossier = self.films / "Wicked (2024)"
        with mock.patch.object(self.A, "themerr_for", return_value=(None, "pas de thème dans ThemerrDB pour ce titre")) as t:
            ok, msg = self.A._auto_one(dossier, "Wicked", kind="movie")
            self.assertFalse(ok)
            ok2, msg2 = self.A._auto_one(dossier, "Wicked", kind="movie")
        self.assertEqual(t.call_count, 1)                                # la 2e fois : aucune recherche
        self.assertIn("vérifié le", msg2)
        self.assertIn("ThemerrDB", msg2)                                 # même groupe dans le compte rendu

    def test_panne_jamais_retenue(self):
        dossier = self.films / "Wicked (2024)"
        with mock.patch.object(self.A, "themerr_for", return_value=(None, "ThemerrDB a répondu 503 (identifiant TheMovieDB 1)")) as t:
            ok, msg = self.A._auto_one(dossier, "Wicked", kind="movie")
            self.A._auto_one(dossier, "Wicked", kind="movie")
        self.assertTrue(msg.startswith(self.A.TRANSIENT))               # pas mis de côté, retenté au prochain lot
        self.assertEqual(t.call_count, 2)
        self.assertIsNone(self.A.absent_recent(dossier))

    def test_absence_ancienne_reverifiee(self):
        dossier = self.films / "Wicked (2024)"
        self.A.absent_noter(dossier, "rien")
        d = self.A._absents()
        d[str(dossier)]["date"] = "2026-01-01"
        self.A._absents_ecrire(d)
        self.assertIsNone(self.A.absent_recent(dossier))


class VoisinTest(AppliBase):
    def setUp(self):
        super().setUp()
        self._cle = os.environ.get("MOUFL_CLE_VOISINES")
        os.environ["MOUFL_CLE_VOISINES"] = "cle-essai"
        self.c = self.A.app.test_client()
        self.h = {"X-MouFl-Cle": "cle-essai"}

    def tearDown(self):
        os.environ.pop("MOUFL_CLE_VOISINES", None) if self._cle is None else os.environ.__setitem__("MOUFL_CLE_VOISINES", self._cle)
        super().tearDown()

    def attendre(self, job):
        for _ in range(100):
            st = self.c.get(f"/api/voisin/job/{job}", headers=self.h).get_json()
            if st.get("done"):
                return st["result"][0]
            time.sleep(0.02)
        self.fail("opération jamais terminée")

    def test_generique_cherche_a_la_demande(self):
        dossier = str(self.films / "Wicked (2024)")
        with mock.patch.object(self.A, "_auto_one", return_value=(True, "Wicked (ThemerrDB) · Emby actualise")) as auto:
            r = self.c.post("/api/voisin/generique/auto", json={"dossier": dossier}, headers=self.h).get_json()
            res = self.attendre(r["job"])
        self.assertEqual((res["ok"], r["id"]), (True, "0/Wicked (2024)"))
        self.assertEqual(auto.call_args.kwargs["kind"], "movie")

    def test_deja_un_generique_ou_titre_inconnu(self):
        r = self.c.post("/api/voisin/generique/auto", json={"dossier": str(self.films / "Dune (2021)")}, headers=self.h).get_json()
        self.assertTrue(r["deja"])
        r = self.c.post("/api/voisin/generique/auto", json={"dossier": "/etc"}, headers=self.h)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.c.post("/api/voisin/generique/auto", json={"dossier": "/etc"}).status_code, 403)   # sans clé

    def test_arrivees_avec_generique_et_poster(self):
        elements = [{"titre": "Wicked", "annee": "2024", "nouveau": True, "poster": True, "saisons": [], "saisons_faites": [],
                     "media_type": "movie", "dossier": str(self.films / "Wicked (2024)")},
                    {"titre": "Dune", "annee": "2021", "nouveau": True, "poster": False, "saisons": [], "saisons_faites": [],
                     "media_type": "movie", "dossier": str(self.films / "Dune (2021)")}]
        with mock.patch.object(self.A.voisins, "appeler", return_value={"ok": True, "elements": elements}):
            arr = self.A._arrivees("2026-10-26T02:00:00Z", set())
        self.assertEqual(arr["posters"], 1)
        self.assertIn("  🎬 Wicked (2024) — 🎵 à chercher · 🖼️ à faire", arr["lignes"])
        self.assertIn("  🎬 Dune (2021) — 🎵 ✓ · 🖼️ ✓", arr["lignes"])
        with mock.patch.object(self.A.voisins, "appeler", return_value={"ok": True, "elements": elements[:1]}):
            arr = self.A._arrivees("2026-10-26T02:00:00Z", {str(self.films / "Wicked (2024)")})
        self.assertIn("posé cette nuit", arr["lignes"][0])


if __name__ == "__main__":
    unittest.main()
