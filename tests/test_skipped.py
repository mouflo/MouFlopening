import tempfile
import unittest
from pathlib import Path

from src import skipped


class SkippedTest(unittest.TestCase):
    def test_add_remove(self):
        with tempfile.TemporaryDirectory() as d:
            skipped.init(Path(d) / "skipped.json")
            self.assertEqual(skipped.all_keys(), set())
            skipped.add(Path("/a/b"))
            skipped.add(Path("/a/b"))
            self.assertEqual(skipped.all_keys(), {"/a/b"})
            skipped.remove(Path("/a/b"))
            skipped.remove(Path("/a/b"))
            self.assertEqual(skipped.all_keys(), set())

    def test_ancien_format_et_raison(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "skipped.json"
            f.write_text(json.dumps(["/x/a", "/x/b"]))
            skipped.init(f)
            self.assertEqual(skipped.all_keys(), {"/x/a", "/x/b"})
            skipped.add(Path("/y/c"), "aucun générique trouvé")
            self.assertEqual(skipped.entries()["/y/c"]["reason"], "aucun générique trouvé")

    def test_reessayer_apres_n_jours(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "skipped.json"
            f.write_text(json.dumps({"/old": {"reason": "", "date": "2020-01-01"}, "/new": {"reason": "", "date": "2999-01-01"}}))
            skipped.init(f)
            self.assertEqual(skipped.all_keys(30), {"/new"})
            self.assertEqual(skipped.all_keys(0), {"/old", "/new"})

    def test_reessayer_un_onglet(self):
        with tempfile.TemporaryDirectory() as d:
            skipped.init(Path(d) / "skipped.json")
            for p in ("/lib/Manga/A", "/lib/Manga/A/s1", "/lib/Films/B", "/lib/Manga2/C"):
                skipped.add(Path(p))
            self.assertEqual(skipped.clear_under(["/lib/Manga"]), 2)
            self.assertEqual(skipped.all_keys(), {"/lib/Films/B", "/lib/Manga2/C"})


if __name__ == "__main__":
    unittest.main()
