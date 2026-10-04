"""
Classe abstraite de base pour les sources de thèmes
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ThemeResult:
    """Résultat d'une recherche de thème"""
    title: str
    source: str
    url: str
    duration: Optional[int] = None
    artist: Optional[str] = None
    quality: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BaseSource(ABC):
    """Classe abstraite pour les sources de thèmes"""

    name: str = "Unknown Source"
    priority: int = 999

    def __init__(self, config: Dict[str, Any]):
        """
        Initialiser la source avec sa configuration

        Args:
            config: Dictionnaire de configuration de la source
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.priority = config.get('priority', 999)

    @abstractmethod
    def search(self, title: str, media_type: str = 'auto') -> Optional[ThemeResult]:
        """
        Chercher un thème pour un titre donné

        Args:
            title: Titre du film/série
            media_type: Type de média ('tv', 'movie', 'anime', ou 'auto')

        Returns:
            ThemeResult si trouvé, None sinon
        """
        pass

    @abstractmethod
    def download(self, url: str, output_path: Path) -> bool:
        """
        Télécharger et encoder un thème

        Args:
            url: URL de la ressource
            output_path: Chemin où sauvegarder le fichier

        Returns:
            True si succès, False sinon
        """
        pass

    def validate_config(self) -> bool:
        """
        Valider que la configuration est correcte pour cette source

        Returns:
            True si config valide
        """
        return self.enabled

    def __lt__(self, other):
        """Comparaison par priorité pour tri"""
        return self.priority < other.priority

    def __repr__(self):
        return f"{self.name}(priority={self.priority}, enabled={self.enabled})"
