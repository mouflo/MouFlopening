"""
Client Emby minimal : prévient Emby qu'un dossier précis a changé
(actualisation ciblée, sans rescanner toute la bibliothèque).
"""

import logging
from pathlib import Path
from typing import Any, Dict

import requests

logger = logging.getLogger(__name__)


class EmbyClient:
    def __init__(self, config: Dict[str, Any]):
        self.host = config.get("host", "").rstrip("/")
        self.api_key = config.get("api_key", "")
        self.timeout = config.get("timeout", 30)

    @property
    def configured(self) -> bool:
        return bool(self.host and self.api_key and "your_emby" not in self.api_key)

    def refresh_path(self, path: Path) -> bool:
        """Signale à Emby que ce chemin a été modifié."""
        if not self.configured:
            logger.warning("[Emby] Non configuré (clé API manquante) : actualisation ignorée")
            return False
        try:
            resp = requests.post(
                f"{self.host}/Library/Media/Updated",
                params={"api_key": self.api_key},
                json={"Updates": [{"Path": str(path), "UpdateType": "Modified"}]},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            logger.info("[Emby] Actualisation demandée : %s", path)
            return True
        except requests.RequestException as e:
            logger.error("[Emby] Échec de l'actualisation : %s", e)
            return False
