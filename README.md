# MouFlopening 🎬🎵

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

Automatic theme song downloader and integrator for Emby/Plex/Jellyfin media servers.

## Features

- 🎵 **Multiple Theme Sources**: AnimeThemes, YouTube, Spotify, and Local files
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

This project is licensed under the MIT License - see LICENSE file for details.
