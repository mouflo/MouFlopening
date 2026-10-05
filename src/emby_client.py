"""
Actualisation ciblée d'Emby : après l'ajout d'un thème, Emby ne relit que CETTE série,
sans rescanner toute la médiathèque. Même méthode que MouFloster.

Clé : data/secrets.env (EMBY_API_KEY), jamais sur GitHub.
Facultatifs : EMBY_URL, EMBY_REFRESH_MODE (ValidationOnly | Default | FullRefresh).
"""

import logging
import os
import re
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


class EmbyError(Exception):
    pass


class EmbyClient:
    def __init__(self, config: Dict[str, Any]):
        self.host = (config.get("host") or "").rstrip("/")
        self.api_key = (config.get("api_key") or "").strip()
        self.timeout = config.get("timeout", 8)

    @property
    def configured(self) -> bool:
        return bool(self.host and self.api_key and "your_emby" not in self.api_key and "cle api" not in self.api_key.lower())

    def describe(self) -> str:
        return f"configuré ({self.host})" if self.configured else "NON configuré (clé API manquante)"

    def _request(self, method: str, path: str, **kwargs):
        headers = {"X-Emby-Token": self.api_key, "Accept": "application/json"}
        try:
            resp = requests.request(method, self.host + path, headers=headers, timeout=self.timeout, **kwargs)
        except requests.exceptions.ConnectionError:
            raise EmbyError(f"Emby injoignable ({self.host})")
        except requests.exceptions.Timeout:
            raise EmbyError("Emby ne répond pas (délai dépassé)")
        except requests.exceptions.RequestException as e:
            raise EmbyError(f"Erreur de connexion à Emby : {e}")
        if resp.status_code in (401, 403):
            raise EmbyError("Clé API Emby refusée (vérifie EMBY_API_KEY)")
        if resp.status_code >= 400:
            raise EmbyError(f"Emby a répondu {resp.status_code}")
        return resp

    def _find_series(self, folder_name: str, titles: List[str]):
        for term in dict.fromkeys(t for t in [re.sub(r"\(\d{4}\)\s*$", "", folder_name).strip(), *titles] if t):
            data = self._request("GET", "/Items", params={
                "Recursive": "true", "IncludeItemTypes": "Series", "SearchTerm": term,
                "Fields": "Path", "Limit": 30}).json()
            for item in data.get("Items", []) if isinstance(data, dict) else []:
                if folder_name in re.split(r"[\\/]", item.get("Path") or ""):
                    return item
        return None

    def refresh_series(self, folder_name: str, title: str = "") -> Dict[str, Any]:
        """Actualise la série dont le dossier s'appelle folder_name. Ne lève jamais d'exception."""
        if not self.configured:
            return {"ok": False, "message": "Emby non configuré (clé API manquante)"}
        try:
            item = self._find_series(folder_name, [title])
            if not item:
                return {"ok": False, "message": f"« {folder_name} » introuvable dans Emby (pas encore scanné ?). Thème copié quand même."}
            mode = os.getenv("EMBY_REFRESH_MODE", "ValidationOnly")
            if mode not in ("ValidationOnly", "Default", "FullRefresh"):
                mode = "ValidationOnly"
            self._request("POST", f"/Items/{item['Id']}/Refresh", params={
                "Recursive": "false", "ImageRefreshMode": mode, "MetadataRefreshMode": mode,
                "ReplaceAllImages": "false", "ReplaceAllMetadata": "false"})
            logger.info("[Emby] Actualisation demandée : %s", item.get("Name") or folder_name)
            return {"ok": True, "message": f"Emby actualise « {item.get('Name') or folder_name} »"}
        except EmbyError as e:
            return {"ok": False, "message": str(e)}
        except Exception as e:
            return {"ok": False, "message": f"Erreur Emby inattendue : {e}"}
