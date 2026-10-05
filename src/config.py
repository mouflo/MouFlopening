"""Chargement de la configuration : config.example.json (valeurs par défaut) + config.json + secrets locaux."""

import json
import os
from pathlib import Path
from typing import Any, Dict

BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_FILE = BASE_DIR / "data" / "secrets.env"


def _merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in over.items():
        out[key] = _merge(base[key], value) if isinstance(value, dict) and isinstance(base.get(key), dict) else value
    return out


def load_secrets_env() -> None:
    """Charge data/secrets.env (clés, identifiants) dans l'environnement. Jamais versionné."""
    if not SECRETS_FILE.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(SECRETS_FILE, override=True)
    except ImportError:
        for line in SECRETS_FILE.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip("'\"")


def load_config(path: str = "config.json") -> Dict[str, Any]:
    example = BASE_DIR / "config.example.json"
    config = json.loads(example.read_text()) if example.exists() else {}
    cfg_path = Path(path)
    if not cfg_path.is_absolute() and not cfg_path.exists():
        cfg_path = BASE_DIR / path
    if cfg_path.exists():
        config = _merge(config, json.loads(cfg_path.read_text()))

    load_secrets_env()
    emby = config.setdefault("emby", {})
    if os.getenv("EMBY_API_KEY"):
        emby["api_key"] = os.environ["EMBY_API_KEY"].strip()
    if os.getenv("EMBY_URL"):
        emby["host"] = os.environ["EMBY_URL"].strip().rstrip("/")
    return config
