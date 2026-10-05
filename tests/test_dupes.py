import tempfile
import unittest
from pathlib import Path

from src import dupes


def mk(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class TestDupes(unittest.TestCase):
    def test_detection(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "Animes"
            a = b"A" * 9000
            b = b"B" * 9000
            mk(root / "Naruto" / "theme.mp3", a)
            mk(root / "Naruto" / "Season 1" / "theme.mp3", a)          # saison 1 = série : aussi un doublon (Emby relancerait la musique)
            mk(root / "Naruto" / "Season 2" / "theme.mp3", a)          # doublon
            mk(root / "Naruto" / "Season 3" / "theme.mp3", b)          # différent : bon
            mk(root / "Bleach" / "Season 1" / "theme.mp3", b)
            mk(root / "Bleach" / "Season 2" / "theme.mp3", b)          # doublon de la saison 1 (pas de thème de série)
            mk(root / "Film seul" / "theme.mp3", a)
            res = {x["series"]: x for x in dupes.find_duplicates([str(root)])}
            self.assertEqual([x["number"] for x in res["Naruto"]["dups"]], [1, 2])
            self.assertEqual(res["Naruto"]["keep"], "série")
            self.assertEqual([x["number"] for x in res["Bleach"]["dups"]], [2])
            self.assertEqual(res["Bleach"]["keep"], "1")
            self.assertNotIn("Film seul", res)
            self.assertEqual(res["Naruto"]["dups"][1]["id"], "0/Naruto/Season 2")

    def test_registre(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "s.json"
            dupes.remember_source(f, Path("/x/y"), "https://a/b.ogg")
            self.assertEqual(dupes.load_sources(f), {"/x/y": "https://a/b.ogg"})


if __name__ == "__main__":
    unittest.main()
