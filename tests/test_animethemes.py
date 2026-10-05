import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile, sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sources.animethemes import AnimeThemesSource
from src.library import clean_title, missing_themes

API = {"anime": [
    {"name": "Fairy Tail", "animesynonyms": [{"text": "FT"}],
     "animethemes": [
         {"type": "ED", "sequence": 1, "slug": "ED1", "animethemeentries": [{"videos": [{"link": "https://v/ed1.webm", "audio": {"link": "https://a/ed1.ogg"}}]}]},
         {"type": "OP", "sequence": 2, "slug": "OP2", "animethemeentries": [{"videos": [{"link": "https://v/op2.webm", "audio": {"link": "https://a/op2.ogg"}}]}]},
         {"type": "OP", "sequence": 1, "slug": "OP1", "animethemeentries": [{"videos": [{"link": "https://v/op1.webm", "audio": None}]}]},
     ]},
    {"name": "Autre chose", "animesynonyms": [], "animethemes": []},
]}


class TestAnimeThemes(unittest.TestCase):
    def source(self):
        return AnimeThemesSource({"enabled": True})

    def mock_get(self, payload):
        resp = MagicMock(); resp.json.return_value = payload; resp.raise_for_status.return_value = None
        return patch("requests.Session.get", return_value=resp)

    def test_prefers_op1_and_falls_back_to_video(self):
        with self.mock_get(API):
            r = self.source().search("Fairy Tail")
        self.assertEqual(r.metadata["slug"], "OP1")
        self.assertEqual(r.url, "https://v/op1.webm")   # pas d'audio -> vidéo

    def test_synonym_match(self):
        with self.mock_get(API):
            self.assertIsNotNone(self.source().search("FT"))

    def test_no_match(self):
        with self.mock_get(API):
            self.assertIsNone(self.source().search("Zzzzzz Qqqq"))

    def test_movie_ignored(self):
        self.assertIsNone(self.source().search("Fairy Tail", "movie"))

    def test_api_error(self):
        import requests
        with patch("requests.Session.get", side_effect=requests.ConnectionError("x")):
            self.assertIsNone(self.source().search("Fairy Tail"))


class TestLibrary(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(clean_title("Fairy Tail (2009) [tvdbid-79]"), "Fairy Tail")
        self.assertEqual(clean_title("Hunter x Hunter {tmdb-1}"), "Hunter x Hunter")

    def test_missing_themes(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ["A", "B", "@eaDir", ".hidden"]:
                (Path(d) / name).mkdir()
            (Path(d) / "B" / "theme.mp3").write_bytes(b"x")
            self.assertEqual([t for t, _ in missing_themes([d])], ["A"])


if __name__ == "__main__":
    unittest.main()
