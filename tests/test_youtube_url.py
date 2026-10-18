import unittest
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
