import tempfile
import unittest
from pathlib import Path

from src import library


class TestThemeUtilisable(unittest.TestCase):
    def test_vide_ou_tronque_compte_comme_absent(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "theme.mp3"
            self.assertIsNone(library.find_theme(Path(d)))
            f.write_bytes(b"")
            self.assertIsNone(library.find_theme(Path(d)))
            f.write_bytes(b"x" * 100)
            self.assertIsNone(library.find_theme(Path(d)))
            f.write_bytes(b"x" * library.MIN_THEME_BYTES)
            self.assertEqual(library.find_theme(Path(d)), f)


if __name__ == "__main__":
    unittest.main()
