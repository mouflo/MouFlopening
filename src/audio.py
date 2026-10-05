"""
Conversion en MP3 avec normalisation du volume.

Le niveau cible s'exprime en dB comme dans MP3Gain / ReplayGain : 89 dB est la référence (celle par défaut de
MP3Gain). Chaque thème est mesuré (filtre ReplayGain de ffmpeg), puis ramené exactement à ce niveau pendant
l'encodage : un seul passage de compression, pas de saut de 1,5 dB comme MP3Gain. Un limiteur à -1 dBFS évite
la saturation quand il faut monter le volume d'un morceau très dynamique.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

REFERENCE_DB = 89.0   # niveau pour lequel ReplayGain annonce un gain de 0 dB
_GAIN_RE = re.compile(r"track_gain\s*=\s*([+-]?\d+(?:\.\d+)?)\s*dB")
_PEAK_RE = re.compile(r"track_peak\s*=\s*(\d+(?:\.\d+)?)")


def measure_gain(path: Path) -> Optional[Tuple[float, float]]:
    """(gain ReplayGain en dB, crête 0..1) du fichier, ou None si la mesure échoue."""
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "replaygain", "-f", "null", "-"],
            capture_output=True, text=True, timeout=180).stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.error("[Audio] Mesure impossible : %s", e)
        return None
    gain, peak = _GAIN_RE.search(out), _PEAK_RE.search(out)
    if not gain:
        logger.error("[Audio] Mesure du volume illisible (piste vide ?) : %s", out[-300:].replace("\n", " "))
        return None
    return float(gain.group(1)), float(peak.group(1)) if peak else 1.0


def convert_to_mp3(src: Path, dst: Path, target_db: float = REFERENCE_DB) -> bool:
    """Convertit src en MP3 (VBR haute qualité) ramené à target_db. True si succès."""
    measured = measure_gain(src)
    if measured is None:
        return False
    gain = measured[0] + (target_db - REFERENCE_DB)
    logger.info("[Audio] Gain appliqué : %+.2f dB (cible %.1f dB)", gain, target_db)

    chain = f"volume={gain:.2f}dB,alimiter=limit=0.89:level=disabled"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-af", chain,
           "-codec:a", "libmp3lame", "-q:a", "2", str(dst)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    except FileNotFoundError:
        logger.error("[Audio] ffmpeg introuvable (apt install ffmpeg)")
        return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.error("[Audio] Conversion MP3 échouée : %s", getattr(e, "stderr", e))
        return False

    check = measure_gain(dst)
    if check is not None:
        level = REFERENCE_DB - check[0]     # gain restant à appliquer pour atteindre 89 dB = écart à 89
        note = "" if abs(level - target_db) < 0.6 else " (limiteur actif : morceau très dynamique)"
        logger.info("[Audio] Niveau final mesuré : %.1f dB%s", level, note)
    return True
