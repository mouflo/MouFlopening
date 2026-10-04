#!/usr/bin/env python3
"""
MouFlopening - Theme song downloader and Emby integrator
Main application entry point and CLI interface
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
import click

from src.sources.base_source import BaseSource, ThemeResult
from src.sources.animethemes import AnimeThemesSource


class MouFlopening:
    """Main application class for MouFlopening"""

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
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logging.info(f"Configuration loaded from {config_path}")
            return config
        except FileNotFoundError:
            logging.error(f"Configuration file not found: {config_path}")
            logging.info(f"Copy config.example.json to {config_path} and configure")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in configuration: {e}")
            sys.exit(1)

    def _setup_logging(self) -> None:
        """Configure logging based on configuration"""
        log_config = self.config.get('logging', {})
        log_level = log_config.get('level', 'INFO')
        log_file = log_config.get('file', 'mouflopening.log')

        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )

    def _initialize_sources(self) -> None:
        """Initialize all configured theme sources"""
        sources_config = self.config.get('sources', {})

        # Initialize AnimeThemes source
        if sources_config.get('animethemes', {}).get('enabled', False):
            try:
                animethemes = AnimeThemesSource(sources_config['animethemes'])
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

    def download_theme(self, title: str, media_type: str = 'auto') -> Optional[str]:
        """
        Download a theme song for given title

        Args:
            title: Title of movie/series
            media_type: Type of media (tv, movie, anime, auto)

        Returns:
            Path to downloaded file if successful, None otherwise
        """
        logging.info(f"Searching for theme: {title} ({media_type})")

        for source in self.sources:
            try:
                result = source.search(title, media_type)
                if result:
                    logging.info(f"Found: {result.title} from {result.source}")
                    # TODO: Download and process the theme
                    return None
            except Exception as e:
                logging.error(f"Error searching {source.name}: {e}")
                continue

        logging.warning(f"No theme found for: {title}")
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

    def scan_missing(self) -> None:
        """Scan library for media without themes"""
        logging.info("Scanning for missing themes...")
        # TODO: Implement library scanning
        pass

    def trigger_emby_scan(self) -> None:
        """Trigger Emby library refresh"""
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
        """Display interactive menu for user"""
        while True:
            click.clear()
            click.echo("=" * 50)
            click.echo("MouFlopening - Theme Downloader")
            click.echo("=" * 50)
            click.echo()
            click.echo("1. Download single theme")
            click.echo("2. Batch download themes")
            click.echo("3. Scan for missing themes")
            click.echo("4. Trigger Emby scan")
            click.echo("5. Exit")
            click.echo()

            choice = click.prompt("Choose an option", type=int)

            if choice == 1:
                title = click.prompt("Enter media title")
                media_type = click.prompt("Media type (auto/tv/movie/anime)", default="auto")
                self.download_theme(title, media_type)
                click.pause()

            elif choice == 2:
                titles_file = click.prompt("Path to titles file")
                self.batch_download(titles_file)
                click.pause()

            elif choice == 3:
                self.scan_missing()
                click.pause()

            elif choice == 4:
                self.trigger_emby_scan()
                click.pause()

            elif choice == 5:
                click.echo("Goodbye!")
                break


@click.command()
@click.option('--config', default='config.json', help='Path to configuration file')
@click.option('--interactive', is_flag=True, help='Interactive menu mode')
@click.option('--download', type=str, help='Download single theme by title')
@click.option('--batch', type=str, help='Batch download from file')
@click.option('--scan-missing', is_flag=True, help='Scan library for missing themes')
def main(config: str, interactive: bool, download: str, batch: str, scan_missing: bool) -> None:
    """MouFlopening - Theme song downloader and Emby integrator"""

    app = MouFlopening(config)

    if download:
        app.download_theme(download)
    elif batch:
        app.batch_download(batch)
    elif scan_missing:
        app.scan_missing()
    elif interactive or not any([download, batch, scan_missing]):
        app.show_interactive_menu()


if __name__ == '__main__':
    main()
