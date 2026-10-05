import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile, sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sources.animethemes import AnimeThemesSource
from src.library import clean_title, missing_themes, resolve_folder, resolve_target, list_library, parse_season_folder, season_query, missing_season_themes

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

    def test_season_folders(self):
        for name, n in [("Season 1", 1), ("Saison 02", 2), ("S03", 3), ("season_10", 10), ("Specials", 0)]:
            self.assertEqual(parse_season_folder(name), n, name)
        for name in ["Extras", "Season", "Seasonal", "backdrops", "S"]:
            self.assertIsNone(parse_season_folder(name), name)
        self.assertEqual(season_query("Fairy Tail", 1), "Fairy Tail")
        self.assertEqual(season_query("Fairy Tail", 2), "Fairy Tail Season 2")

    def test_season_targets(self):
        with tempfile.TemporaryDirectory() as d:
            s = Path(d) / "Serie"
            for n in ["Season 1", "Season 2", "Specials", "Extras"]:
                (s / n).mkdir(parents=True)
            (s / "Season 1" / "theme.mp3").write_bytes(b"x")
            lib = list_library([d])[0]
            self.assertEqual([(x["number"], x["has_theme"]) for x in lib["seasons"]], [(0, False), (1, True), (2, False)])
            self.assertEqual(resolve_target([d], "0/Serie/Season 2"), (s / "Season 2", s, 2))
            self.assertEqual(resolve_target([d], "0/Serie"), (s, s, None))
            for bad in ["0/Serie/Extras", "0/Serie/../x", "0/Serie/Season 9", "0/Serie/Season 1/x"]:
                self.assertEqual(resolve_target([d], bad), (None, None, None), bad)
            self.assertEqual([(t, n) for t, n, _, _ in missing_season_themes([d])], [("Serie", 2)])  # ni saison 1 (déjà faite) ni Specials


class TestUrlSafety(unittest.TestCase):
    def test_allowed_urls(self):
        ok = AnimeThemesSource.is_allowed_url
        self.assertTrue(ok("https://a.animethemes.moe/x.ogg"))
        self.assertTrue(ok("https://animethemes.moe/x"))
        for bad in ["http://a.animethemes.moe/x", "https://animethemes.moe.evil.com/x", "https://evil.com/animethemes.moe", "file:///etc/passwd", ""]:
            self.assertFalse(ok(bad), bad)


class TestAudio(unittest.TestCase):
    def test_normalizes_to_89_db(self):
        import shutil, subprocess
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg absent")
        from src.audio import convert_to_mp3, measure_gain
        with tempfile.TemporaryDirectory() as d:
            for name, amp in [("quiet", 0.05), ("loud", 0.7)]:
                wav, mp3 = Path(d) / f"{name}.wav", Path(d) / f"{name}.mp3"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i",
                                f"anoisesrc=color=pink:duration=6:amplitude={amp}", str(wav)], check=True)
                self.assertTrue(convert_to_mp3(wav, mp3, 89.0))
                self.assertLess(abs(measure_gain(mp3)[0]), 0.6, name)   # gain restant ≈ 0 dB = niveau 89 dB


if __name__ == "__main__":
    unittest.main()


class TestFindTheme(unittest.TestCase):
    def test_find_theme(self):
        import tempfile
        from pathlib import Path
        from src.library import find_theme
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            self.assertIsNone(find_theme(d))
            (d / "theme-music").mkdir()
            (d / "theme-music" / "naruto-theme.mp3").write_bytes(b"x")
            self.assertEqual(find_theme(d).name, "naruto-theme.mp3")
            (d / "theme.ogg").write_bytes(b"x")
            self.assertEqual(find_theme(d).name, "theme.ogg")
