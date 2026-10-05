import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from flask import Flask

import nightly_settings
from src import nightly

TOKEN = "123456789:" + "A" * 35


class TestNightly(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        nightly.init(Path(self.d.name) / "data" / "nightly.json")
        self.app = Flask(__name__)
        self.ran = []
        nightly_settings.init_app(self.app, self.d.name, nightly, lambda: self.ran.append(1), lambda: False)
        self.c = self.app.test_client()
        for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.d.cleanup()

    def test_rapport_vide_pas_de_message(self):
        self.assertIsNone(nightly.format_report([{"kind": "movie", "added": [], "failed": 4}], 60))

    def test_rapport(self):
        t = nightly.format_report([{"kind": "movie", "added": ["A (2020)"], "failed": 2}], 130, datetime(2026, 10, 6, 3, 0))
        self.assertIn("mardi 6 octobre", t)
        self.assertIn("✅ A (2020)", t)
        self.assertIn("1 nouveau thème", t)
        self.assertIn("2 titres sans thème", t)

    def test_reglages(self):
        self.assertEqual(self.c.post("/api/nightly", json={"enabled": True, "hour": 25}).status_code, 400)
        self.assertTrue(self.c.post("/api/nightly", json={"enabled": True, "hour": 4}).get_json()["ok"])
        s = self.c.get("/api/nightly").get_json()
        self.assertTrue(s["enabled"]); self.assertEqual(s["hour"], 4); self.assertFalse(s["telegram"])

    def test_telegram_jeton_invalide(self):
        r = self.c.post("/api/settings/telegram", json={"token": "abc", "chat_id": "123456"})
        self.assertEqual(r.status_code, 400)

    def test_telegram_enregistre_sans_exposer_le_jeton(self):
        with mock.patch.object(nightly, "check_bot", return_value=(True, "ok")), mock.patch.object(nightly, "send", return_value=(True, "ok")):
            r = self.c.post("/api/settings/telegram", json={"token": TOKEN, "chat_id": "987654321"})
        self.assertTrue(r.get_json()["ok"])
        self.assertIn(TOKEN, (Path(self.d.name) / "data" / "secrets.env").read_text())
        s = self.c.get("/api/nightly").get_json()
        self.assertTrue(s["telegram"])
        self.assertNotIn(TOKEN, str(s))

    def test_envoi_erreur_ne_montre_pas_le_jeton(self):
        import requests
        with mock.patch("requests.post", side_effect=requests.exceptions.ConnectionError("https://api.telegram.org/bot" + TOKEN)):
            ok, msg = nightly.send("x", TOKEN, "123456")
        self.assertFalse(ok); self.assertNotIn(TOKEN, msg)


if __name__ == "__main__":
    unittest.main()
