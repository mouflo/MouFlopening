"""
Éditeur audio (découpe + fondus) : préparation d'une copie de travail, courbe du son, et rendu final.
- La copie de travail est un MP3 gardé dans data/edit/ (supprimé après 6 h) ; le thème en place n'est touché qu'à l'enregistrement
- La courbe est calculée ici (un point min/max tous les 10 ms) : la page n'a pas à décoder tout le son
"""
import array
import json
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

BINS_PER_SEC = 100
_TOKEN = re.compile(r"^[0-9a-f]{32}$")
KEEP_SECONDS = 6 * 3600


def edit_dir(base: Path) -> Path:
    d = base / "data" / "edit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_token() -> str:
    return uuid.uuid4().hex


def valid_token(token: str) -> bool:
    return bool(_TOKEN.match(token or ""))


def cleanup(base: Path) -> None:
    now = time.time()
    try:
        for f in edit_dir(base).iterdir():
            if now - f.stat().st_mtime > KEEP_SECONDS:
                f.unlink()
    except OSError:
        pass


def duration(path: Path) -> float:
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return float(out)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return 0.0


def compute_peaks(path: Path) -> dict:
    """{"duration", "bins_per_sec", "peaks": [min0, max0, min1, max1, …]} valeurs de -127 à 127."""
    rate = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
                         capture_output=True, timeout=300).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    per_bin = rate // BINS_PER_SEC
    peaks = []
    for i in range(0, len(samples), per_bin):
        chunk = samples[i:i + per_bin]
        peaks.append(max(-127, min(127, min(chunk) // 256)))
        peaks.append(max(-127, min(127, max(chunk) // 256)))
    return {"duration": round(len(samples) / rate, 3), "bins_per_sec": BINS_PER_SEC, "peaks": peaks}


def stage(base: Path, src: Path, token: Optional[str] = None) -> Optional[dict]:
    """Prépare la copie de travail à partir d'un fichier audio quelconque. -> {"token", "duration"} ou None."""
    cleanup(base)
    token = token or new_token()
    dst = edit_dir(base) / f"{token}.mp3"
    if src.suffix.lower() == ".mp3":
        import shutil
        shutil.copyfile(src, dst)
    else:
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-codec:a", "libmp3lame", "-q:a", "0", str(dst)],
                           capture_output=True, timeout=300)
        if r.returncode != 0:
            return None
    try:
        data = compute_peaks(dst)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    if data["duration"] <= 0:
        return None
    (edit_dir(base) / f"{token}.json").write_text(json.dumps(data), encoding="utf-8")
    return {"token": token, "duration": data["duration"]}


def render(src: Path, dst: Path, start: float, end: float, fade_in: float, fade_out: float) -> bool:
    """Garde [start, end] de src, avec fondu d'entrée et de sortie, et l'écrit dans dst (WAV : la normalisation du volume suit)."""
    length = end - start
    filters = []
    if fade_in > 0:
        filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
    if fade_out > 0:
        filters.append(f"afade=t=out:st={max(0.0, length - fade_out):.3f}:d={fade_out:.3f}")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-vn"]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += [str(dst)]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=300).returncode == 0 and dst.is_file()
    except (OSError, subprocess.TimeoutExpired):
        return False
