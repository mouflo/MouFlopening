import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import ytcookies

GOOD = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tabc\n#HttpOnly_.youtube.com\tTRUE\t/\tTRUE\t1893456000\tHSID\tdef\n"


class TestCookies(unittest.TestCase):
    def test_validation(self):
        self.assertTrue(ytcookies.validate(GOOD)[0])
        self.assertEqual(ytcookies.validate(GOOD)[2], 2)
        self.assertFalse(ytcookies.validate("n'importe quoi")[0])
        self.assertFalse(ytcookies.validate(".example.com\tTRUE\t/\tTRUE\t1\tA\tb")[0])     # pas YouTube

    def test_enregistrement_prive(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "c.txt"
            with mock.patch.object(ytcookies, "COOKIE_FILE", f):
                self.assertEqual(ytcookies.opts(), {})
                ytcookies.save(GOOD)
                self.assertEqual(oct(f.stat().st_mode & 0o777), "0o600")
                self.assertEqual(ytcookies.opts(), {"cookiefile": str(f)})
                ytcookies.clear()
                self.assertFalse(f.exists())


if __name__ == "__main__":
    unittest.main()
