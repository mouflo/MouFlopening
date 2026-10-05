import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile, sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sources.animethemes import AnimeThemesSource
from src.library import clean_title, missing_themes, resolve_folder, list_library

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

    def test_resolve_folder_refuses_escapes(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "Serie").mkdir(); (Path(d) / "@eaDir").mkdir()
            self.assertEqual(resolve_folder([d], "0/Serie"), Path(d) / "Serie")
            for bad in ["../x", "0/..", "0/a/b", "0/@eaDir", "5/Serie", "", "Serie"]:
                self.assertIsNone(resolve_folder([d], bad), bad)

    def test_list_library_states(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "A").mkdir(); (Path(d) / "B").mkdir(); (Path(d) / "B" / "theme.mp3").write_bytes(b"x")
            self.assertEqual([(i["name"], i["has_theme"]) for i in list_library([d])], [("A", False), ("B", True)])


class TestUrlSafety(unittest.TestCase):
    def test_allowed_urls(self):
        ok = AnimeThemesSource.is_allowed_url
        self.assertTrue(ok("https://a.animethemes.moe/x.ogg"))
        self.assertTrue(ok("https://animethemes.moe/x"))
        for bad in ["http://a.animethemes.moe/x", "https://animethemes.moe.evil.com/x", "https://evil.com/animethemes.moe", "file:///etc/passwd", ""]:
            self.assertFalse(ok(bad), bad)


if __name__ == "__main__":
    unittest.main()
