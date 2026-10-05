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
