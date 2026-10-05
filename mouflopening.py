#!/usr/bin/env python3
"""
MouFlopening - Téléchargeur de thèmes musicaux et intégration à Emby
Point d'entrée en ligne de commande (l'interface web est dans app.py)
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import click

from src.sources.base_source import BaseSource, ThemeResult
from src.sources.animethemes import AnimeThemesSource
from src.library import THEME_FILENAME, missing_themes
from src.emby_client import EmbyClient
from src.config import load_config


class MouFlopening:
    """Classe principale de MouFlopening"""

    def __init__(self, config_path: str = "config.json"):
        """
        Initialize MouFlopening with configuration

        Args:
            config_path: Path to configuration JSON file
        """
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.sources: List[BaseSource] = []
        self._initialize_sources()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration (voir src/config.py)"""
        try:
            return load_config(config_path)
        except json.JSONDecodeError as e:
            logging.error(f"JSON invalide dans la configuration : {e}")
            sys.exit(1)

    def _setup_logging(self) -> None:
        """Règle le journal d'après la configuration"""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'mouflopening.log')

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ],
            force=True  # sinon un log émis avant ce point bloque la configuration
        )

    def _initialize_sources(self) -> None:
        """Prépare toutes les sources de thèmes configurées"""
        sources_config = self.config.get('sources', {})

        # Initialize AnimeThemes source
        if sources_config.get('animethemes', {}).get('enabled', False):
            try:
                animethemes = AnimeThemesSource(
                    sources_config['animethemes'],
                    threshold=self.config.get('matching', {}).get('threshold', 70))
                if animethemes.validate_config():
                    self.sources.append(animethemes)
                    logging.info("AnimeThemes source initialized")
            except Exception as e:
                logging.error(f"Failed to initialize AnimeThemes: {e}")

        # TODO: Initialize YouTube source
        # TODO: Initialize Spotify source
        # TODO: Initialize Local source

        # Sort by priority
        self.sources.sort()
        logging.info(f"Initialized {len(self.sources)} theme sources")

    def download_theme(self, title: str, media_type: str = 'auto',
                       output_dir: Optional[Path] = None) -> Optional[str]:
        """
        Cherche et télécharge un thème, l'enregistre sous theme.mp3 dans output_dir.

        Args:
            title: Titre du film/série
            media_type: Type de média (tv, movie, anime, auto)
            output_dir: Dossier de la série (par défaut themes.output_dir/<titre>)

        Returns:
            Chemin du fichier si succès, None sinon
        """
        logging.info(f"Recherche du thème : {title} ({media_type})")
        if output_dir is None:
            base = Path(self.config.get('themes', {}).get('output_dir', 'themes'))
            output_dir = base / title
        target = Path(output_dir) / THEME_FILENAME

        for source in self.sources:
            try:
                result = source.search(title, media_type)
                if not result:
                    continue
                logging.info(f"Trouvé : {result.title} ({result.source})")
                if source.download(result.url, target):
                    return str(target)
            except Exception as e:
                logging.error(f"Erreur avec {source.name} : {e}")
                continue

        logging.warning(f"Aucun thème trouvé pour : {title}")
        return None

    def batch_download(self, titles_file: str) -> None:
        """
        Download themes for multiple titles from a file

        Args:
            titles_file: Path to file with one title per line
        """
        try:
            with open(titles_file, 'r') as f:
                titles = [line.strip() for line in f if line.strip()]

            logging.info(f"Batch downloading {len(titles)} titles")

            for i, title in enumerate(titles, 1):
                logging.info(f"[{i}/{len(titles)}] Processing: {title}")
                self.download_theme(title)

        except FileNotFoundError:
            logging.error(f"Titles file not found: {titles_file}")

    def scan_missing(self, dry_run: bool = False, limit: Optional[int] = None) -> None:
        """Parcourt la médiathèque et télécharge le thème des séries qui n'en ont pas."""
        roots = self.config.get('library', {}).get('paths', [])
        if not roots:
            logging.error("Aucun dossier dans library.paths (config.json)")
            return

        todo = missing_themes(roots)
        logging.info(f"{len(todo)} série(s) sans {THEME_FILENAME}")
        emby = EmbyClient(self.config.get('emby', {}))
        refresh = self.config.get('emby', {}).get('scan_after_download', True)
        done = failed = 0

        for title, folder in todo[:limit]:
            if dry_run:
                logging.info(f"[simulation] {title}  ->  {folder}")
                continue
            if self.download_theme(title, 'anime', folder):
                done += 1
                if refresh:
                    emby.refresh_series(folder.name, title)
            else:
                failed += 1

        logging.info(f"Terminé : {done} thème(s) ajouté(s), {failed} introuvable(s)")

    def trigger_emby_scan(self) -> None:
        """Demande à Emby de relire la médiathèque"""
        emby_config = self.config.get('emby', {})
        emby_host = emby_config.get('host')
        api_key = emby_config.get('api_key')

        if not emby_host or not api_key:
            logging.error("Emby configuration incomplete")
            return

        logging.info(f"Triggering Emby scan at {emby_host}")
        # TODO: Implement Emby API refresh call
        pass

    def show_interactive_menu(self) -> None:
        """Affiche le menu interactif"""
        while True:
            click.clear()
            click.echo("=" * 50)
            click.echo("MouFlopening - Téléchargeur de thèmes")
            click.echo("=" * 50)
            click.echo()
            click.echo("1. Télécharger un thème")
            click.echo("2. Télécharger plusieurs thèmes (fichier de titres)")
            click.echo("3. Chercher les thèmes manquants")
            click.echo("4. Lancer un scan d'Emby")
            click.echo("5. Quitter")
            click.echo()

            choice = click.prompt("Ton choix", type=int)

            if choice == 1:
                title = click.prompt("Titre du film, de la série ou de l'anime")
                media_type = click.prompt("Type (auto/tv/movie/anime)", default="auto")
                self.download_theme(title, media_type)
                click.pause()

            elif choice == 2:
                titles_file = click.prompt("Chemin du fichier de titres")
                self.batch_download(titles_file)
                click.pause()

            elif choice == 3:
                self.scan_missing()
                click.pause()

            elif choice == 4:
                self.trigger_emby_scan()
                click.pause()

            elif choice == 5:
                click.echo("Au revoir !")
                break


@click.command()
@click.option('--config', default='config.json', help='Chemin du fichier de configuration')
@click.option('--interactive', is_flag=True, help='Menu interactif')
@click.option('--download', type=str, help='Télécharge le thème d\'un titre')
@click.option('--batch', type=str, help='Télécharge les thèmes d\'une liste de titres (un par ligne)')
@click.option('--scan-missing', is_flag=True, help='Cherche les thèmes manquants dans la médiathèque')
@click.option('--dry-run', is_flag=True, help='Avec --scan-missing : liste sans rien télécharger')
@click.option('--limit', type=int, default=None, help='Avec --scan-missing : nombre maximum de séries')
def main(config: str, interactive: bool, download: str, batch: str, scan_missing: bool,
         dry_run: bool, limit: int) -> None:
    """MouFlopening - Téléchargeur de thèmes musicaux et intégration à Emby"""

    app = MouFlopening(config)

    if download:
        app.download_theme(download)
    elif batch:
        app.batch_download(batch)
    elif scan_missing:
        app.scan_missing(dry_run=dry_run, limit=limit)
    elif interactive or not any([download, batch, scan_missing]):
        app.show_interactive_menu()


if __name__ == '__main__':
    main()
