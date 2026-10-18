import unittest
import tempfile
from pathlib import Path
from src.sources.youtube import YouTubeSource


class CanonicalUrl(unittest.TestCase):
    def test_formes_youtube(self):
        ok = "https://www.youtube.com/watch?v=abcdefghijk"
        for u in ("https://youtu.be/abcdefghijk?t=5", "https://www.youtube.com/watch?v=abcdefghijk&list=PL1&t=9s",
                  "https://m.youtube.com/watch?v=abcdefghijk", "https://music.youtube.com/watch?v=abcdefghijk",
                  "https://www.youtube.com/shorts/abcdefghijk"):
            self.assertEqual(YouTubeSource.canonical_url(u), ok, u)

    def test_autre_lien_inchange(self):
        self.assertEqual(YouTubeSource.canonical_url(" https://exemple.org/a.mp3 "), "https://exemple.org/a.mp3")


if __name__ == "__main__":
    unittest.main()


class MessageAgeTest(unittest.TestCase):
    def test_video_reservee_aux_adultes_explique_les_cookies(self):
        from src.sources.youtube import _friendly
        m = _friendly("ERROR: [youtube] abc: Sign in to confirm your age. Use --cookies-from-browser or --cookies")
        self.assertIn("réservée aux adultes", m)
        self.assertIn("Cookies YouTube", m)


class CookiesEnDernierRecoursTest(unittest.TestCase):
    def _source(self, reponses):
        from src.sources import youtube as Y
        src = Y.YouTubeSource({})
        appels = []

        def faux(url, tmp, clients=None, max_duration=None, cookies=False):
            appels.append(cookies)
            err = ("" if cookies else reponses[0]) if len(reponses) == 1 else reponses.pop(0)
            if not err:
                (Path(tmp) / "source.webm").write_bytes(b"x")
            return err
        src._yt_download = faux
        return Y, src, appels

    def test_les_cookies_ne_servent_qua_apres_un_refus(self):
        from unittest import mock
        Y, src, appels = self._source(["ERROR: Sign in to confirm your age"])
        with mock.patch.object(Y.ytcookies, "opts", lambda: {"cookiefile": "x"}), \
                mock.patch.object(Y, "_upgrade_ytdlp", lambda force=False: False), \
                mock.patch.object(Y, "convert_to_mp3", lambda f, out, db: (Path(out).write_bytes(b"x"), True)[1]):
            src.download("https://www.youtube.com/watch?v=5MMssGBXVE4", Path(tempfile.mkdtemp()) / "t.mp3")
        self.assertEqual(appels[0], False)
        self.assertIn(True, appels)

    def test_video_normale_jamais_avec_cookies(self):
        from unittest import mock
        Y, src, appels = self._source([""])
        with mock.patch.object(Y.ytcookies, "opts", lambda: {"cookiefile": "x"}), \
                mock.patch.object(Y, "convert_to_mp3", lambda f, out, db: (Path(out).write_bytes(b"x"), True)[1]):
            src.download("https://www.youtube.com/watch?v=dQw4w9WgXcQ", Path(tempfile.mkdtemp()) / "t.mp3")
        self.assertEqual(appels, [False])
