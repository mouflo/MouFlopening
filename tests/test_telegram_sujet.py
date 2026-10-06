"""Telegram dans un sujet de groupe (message_thread_id), sans vrai Telegram."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from flask import Flask

import nightly_settings
from src import nightly

TOKEN = "123456789:" + "A" * 35


class Rep:
    def __init__(self, code=200, data=None):
        self.status_code, self._d = code, data or {}

    def json(self):
        return self._d


class TestSujet(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        nightly.init(Path(self.d.name) / "data" / "nightly.json")
        self.app = Flask(__name__)
        nightly_settings.init_app(self.app, self.d.name, nightly, lambda: None, lambda: False)
        self.c = self.app.test_client()
        self._env = mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "-1001"})
        self._env.start()
        os.environ.pop("TELEGRAM_THREAD_ID", None)

    def tearDown(self):
        self._env.stop()
        self.d.cleanup()

    def test_envoi_sans_puis_avec_sujet(self):
        with mock.patch("requests.post", return_value=Rep()) as p:
            nightly.send("a")
            self.assertNotIn("message_thread_id", p.call_args.kwargs["json"])
            os.environ["TELEGRAM_THREAD_ID"] = "8"
            nightly.send("b")
            self.assertEqual(p.call_args.kwargs["json"]["message_thread_id"], 8)

    def test_sujet_ignore_si_reglages_repris_ailleurs(self):
        os.environ.pop("TELEGRAM_BOT_TOKEN")
        os.environ["TELEGRAM_THREAD_ID"] = "8"
        self.assertEqual(nightly.telegram_thread(), "")

    def test_detection_et_enregistrement(self):
        maj = {"result": [{"message": {"chat": {"type": "supergroup", "id": -1007}, "message_thread_id": 5, "is_topic_message": True}}]}
        with mock.patch("requests.post", return_value=Rep(200, maj)):
            r = self.c.post("/api/settings/telegram", json={"action": "detect"}).get_json()
        self.assertEqual((r["chat_id"], r["thread_id"]), ("-1007", "5"))
        with mock.patch.object(nightly, "check_bot", return_value=(True, "ok")), \
             mock.patch("requests.post", return_value=Rep()) as p:
            r = self.c.post("/api/settings/telegram", json={"token": TOKEN, "chat_id": "-1007", "thread_id": "5"}).get_json()
        self.assertTrue(r["ok"])
        self.assertEqual(p.call_args.kwargs["json"]["message_thread_id"], 5)
        self.assertEqual(os.environ["TELEGRAM_THREAD_ID"], "5")
        self.assertIn("TELEGRAM_THREAD_ID", (Path(self.d.name) / "data" / "secrets.env").read_text())
        self.assertEqual(self.c.get("/api/nightly").get_json()["thread_id"], "5")
        self.assertEqual(self.c.post("/api/settings/telegram", json={"thread_id": "x"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
