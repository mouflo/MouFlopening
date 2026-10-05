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


if __name__ == "__main__":
    unittest.main()
