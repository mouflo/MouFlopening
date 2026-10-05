"""
Cookies YouTube (facultatif) : un fichier « cookies.txt » (format Netscape) exporté de ton navigateur, collé dans les Réglages.
Il évite certains refus de YouTube (« connexion demandée », « vidéo non disponible depuis le serveur »).
Le contenu est gardé dans data/youtube-cookies.txt (droits 600), jamais sur GitHub, jamais renvoyé à la page ni écrit dans le Journal.
"""
import os
import re
import time
from pathlib import Path

COOKIE_FILE = Path(__file__).resolve().parent.parent / "data" / "youtube-cookies.txt"
MAX_BYTES = 600_000
_DOMAIN = re.compile(r"(^|\.)(youtube\.com|google\.com)$", re.I)


def opts() -> dict:
    """Options à ajouter à yt-dlp : {} quand aucun cookie n'est réglé."""
    return {"cookiefile": str(COOKIE_FILE)} if COOKIE_FILE.is_file() else {}


def validate(text: str):
    """(ok, message, nombre de cookies YouTube/Google). Format Netscape : 7 colonnes séparées par des tabulations."""
    if len(text.encode("utf-8")) > MAX_BYTES:
        return False, "Fichier trop gros pour être un fichier de cookies.", 0
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
            continue
        parts = line.split("\t")
        if len(parts) != 7:
            return False, "Format inconnu : il faut un fichier « cookies.txt » (format Netscape), tel qu'exporté par l'extension du navigateur.", 0
        domain = parts[0].replace("#HttpOnly_", "").lstrip(".")
        if _DOMAIN.search(domain):
            n += 1
    if not n:
        return False, "Aucun cookie youtube.com trouvé : connecte-toi à YouTube dans ton navigateur avant d'exporter.", 0
    return True, f"{n} cookies YouTube reconnus.", n


def save(text: str) -> None:
    COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = COOKIE_FILE.with_suffix(".tmp")
    lines = text.replace("\r\n", "\n").strip("\n")
    if not lines.startswith("# Netscape HTTP Cookie File"):
        lines = "# Netscape HTTP Cookie File\n" + lines
    tmp.write_text(lines + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, COOKIE_FILE)


def clear() -> None:
    try:
        COOKIE_FILE.unlink()
    except OSError:
        pass


def state() -> dict:
    if not COOKIE_FILE.is_file():
        return {"configured": False}
    return {"configured": True, "since": time.strftime("%d/%m/%Y", time.localtime(COOKIE_FILE.stat().st_mtime))}
