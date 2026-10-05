import json
import os
import tempfile
import unittest
from pathlib import Path

from flask import Flask

import settings_page


class FakeEmby:
    host = "http://x:8096"


class TestSettingsPage(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.media = Path(self.d.name) / "media"; self.media.mkdir()
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"))
        self.emby = FakeEmby()
        settings_page.init_app(self.app, self.d.name, lambda: "v0", lambda: {}, lambda: [], lambda: [], self.emby, "/sauvegardes")
        self.c = self.app.test_client()

    def tearDown(self):
        self.d.cleanup()

    def test_adresse_emby(self):
        self.assertEqual(self.c.post("/api/settings/emby-host", json={"host": "pas une adresse"}).status_code, 400)
        r = self.c.post("/api/settings/emby-host", json={"host": "http://192.168.1.134:8096/"})
        self.assertTrue(r.get_json()["ok"]); self.assertEqual(self.emby.host, "http://192.168.1.134:8096")
        self.assertIn("EMBY_URL", (Path(self.d.name) / "data" / "secrets.env").read_text())
        os.environ.pop("EMBY_URL", None)

    def test_dossiers(self):
        r = self.c.post("/api/settings/paths", json={"auto_parent": str(self.media / "nope"), "restart": False})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/api/settings/paths", json={"auto_parent": str(self.media), "backup_dir": str(self.media / "old"), "restart": False})
        self.assertTrue(r.get_json()["ok"])
        cfg = json.loads((Path(self.d.name) / "config.json").read_text())
        self.assertEqual(cfg["library"]["auto_parent"], str(self.media))


if __name__ == "__main__":
    unittest.main()


class TestFolders(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        root = Path(self.d.name)
        self.parent = root / "media"
        for n in ("Films HD", "Mes vidéos", "Animes"):
            (self.parent / n).mkdir(parents=True)
        (self.parent / "@eaDir").mkdir()
        self.extra = root / "ailleurs" / "Docu"; self.extra.mkdir(parents=True)
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent.parent / "templates"))
        self.cfg = {}
        settings_page.init_app(self.app, root, lambda: "v0", lambda: self.cfg, lambda: [], lambda: [], FakeEmby(), "/s")
        self.c = self.app.test_client()

    def tearDown(self):
        self.d.cleanup()

    def test_decouverte_exclusion_et_type(self):
        from src import library
        cfg = {"library": {"auto_parent": str(self.parent)}}
        self.assertEqual({c["kind"] for c in library.discover_categories(cfg)}, {"movie", "anime"})
        cfg["library"]["excluded"] = [str(self.parent / "Animes")]
        cfg["library"]["kinds"] = {str(self.parent / "Mes vidéos"): "series"}
        cfg["library"]["categories"] = [{"kind": "series", "path": str(self.extra)}]
        cats = {c["kind"]: c["paths"] for c in library.discover_categories(cfg)}
        self.assertNotIn("anime", cats)
        self.assertEqual(len(cats["series"]), 2)

    def test_enregistrement_dossiers(self):
        self.cfg = {"library": {"auto_parent": str(self.parent)}}
        st = self.c.get("/api/settings/paths").get_json()
        names = {f["name"]: f for f in st["folders"]}
        self.assertNotIn("@eaDir", names)
        self.assertFalse(names["Mes vidéos"]["enabled"])                     # type inconnu : décoché
        folders = [dict(f) for f in st["folders"]]
        for f in folders:
            if f["name"] == "Mes vidéos":
                f["enabled"], f["kind"] = True, "series"
            if f["name"] == "Animes":
                f["enabled"] = False
        folders.append({"path": str(self.extra), "kind": "movie", "enabled": True, "auto": False})
        r = self.c.post("/api/settings/paths", json={"auto_parent": str(self.parent), "folders": folders, "restart": False})
        self.assertTrue(r.get_json()["ok"])
        cfg = json.loads((Path(self.d.name) / "config.json").read_text())["library"]
        self.assertEqual(cfg["excluded"], [str(self.parent / "Animes")])
        self.assertEqual(cfg["kinds"], {str(self.parent / "Mes vidéos"): "series"})
        self.assertEqual(cfg["categories"], [{"kind": "movie", "path": str(self.extra)}])
        bad = [{"path": str(self.parent / "Mes vidéos"), "kind": "", "enabled": True, "auto": True}]
        self.assertEqual(self.c.post("/api/settings/paths", json={"auto_parent": str(self.parent), "folders": bad, "restart": False}).status_code, 400)

    def test_explorateur(self):
        r = self.c.get("/api/fs/list", query_string={"path": str(self.parent)}).get_json()
        self.assertEqual(r["dirs"], ["Animes", "Films HD", "Mes vidéos"])
        self.assertEqual(r["parent"], str(self.parent.parent))
