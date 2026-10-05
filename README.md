# MouFlopening 🎬🎵

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Automatic theme song downloader and integrator for Emby/Plex/Jellyfin media servers.

## 📸 Aperçu

*Captures avec des données de démonstration.*

**La liste des films, séries et animes, avec ceux qui n'ont pas encore de thème**

![La liste des films, séries et animes, avec ceux qui n'ont pas encore de thème](docs/screenshots/liste.png)

**Les propositions pour un titre : la sélection ★ de la base ThemerrDB en tête, puis les résultats YouTube**

![Les propositions pour un titre : la sélection ★ de la base ThemerrDB en tête, puis les résultats YouTube](docs/screenshots/recherche.png)

**La recherche annonce chaque étape en direct (titre original, ThemerrDB, YouTube…)**

![La recherche annonce chaque étape en direct (titre original, ThemerrDB, YouTube…)](docs/screenshots/progression.png)

**Sur téléphone**

![Sur téléphone](docs/screenshots/mobile.png)

## Features

- 🎵 **Sources des thèmes** : AnimeThemes (animes), ThemerrDB et YouTube (films et séries)
- 🎬 **Smart Matching**: Fuzzy string matching for accurate title identification
- 📚 **Batch Processing**: Download themes for multiple titles at once
- 🔄 **Emby Integration**: Automatic library refresh after downloads
- ⚙️ **Flexible Configuration**: JSON-based configuration for all sources
- 🎛️ **Interactive Menu**: User-friendly CLI interface

## Installation

1. Clone the repository:
   ```bash
   cd /opt/MouFlopening
   ```

2. Create virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the application:
   ```bash
   cp config.example.json config.json
   # Edit config.json with your settings
   ```

## Usage

### Interactive Mode
```bash
python mouflopening.py --interactive
```

### Download Single Theme
```bash
python mouflopening.py --download "Attack on Titan"
```

### Batch Download
```bash
python mouflopening.py --batch titles.txt
```

## License

Ce projet est sous licence MIT (voir le fichier `LICENSE`) : tu peux le réutiliser, le modifier et le partager librement.
