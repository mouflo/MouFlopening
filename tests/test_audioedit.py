import shutil
import tempfile
import unittest
from pathlib import Path

from src import audioedit


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg absent")
class TestAudioEdit(unittest.TestCase):
    def test_stage_et_rendu(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            src = base / "s.mp3"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", str(src)], check=True)
            st = audioedit.stage(base, src)
            self.assertTrue(audioedit.valid_token(st["token"]))
            self.assertAlmostEqual(st["duration"], 5.0, delta=0.2)
            out = base / "o.wav"
            self.assertTrue(audioedit.render(audioedit.edit_dir(base) / f"{st['token']}.mp3", out, 1.0, 3.0, 0.5, 0.5))
            self.assertAlmostEqual(audioedit.duration(out), 2.0, delta=0.1)

    def test_jeton(self):
        self.assertFalse(audioedit.valid_token("../../etc/passwd"))
        self.assertFalse(audioedit.valid_token(""))


if __name__ == "__main__":
    unittest.main()
