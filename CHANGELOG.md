# Changelog

## [0.2.0] - 2026-10-05

### Ajouté
- **Interface web** (port 8001) : connexion par formulaire, thème sombre Emby, choix manuel avec écoute, mode automatique, lot avec barre de progression, fenêtre Journal copiable, numéro de version affiché
- Identifiant et clé Emby repris automatiquement de MouFloster au déploiement
- Source AnimeThemes fonctionnelle : recherche (titres alternatifs inclus), choix du générique (OP1 puis ED1), téléchargement et conversion en MP3 via ffmpeg
- Analyse de la médiathèque (`--scan-missing`, avec `--dry-run` et `--limit`) : enregistre `theme.mp3` dans le dossier de chaque série qui n'en a pas
- Actualisation ciblée d'Emby (uniquement la série modifiée) après chaque téléchargement
- Clé API Emby stockée localement via `set-secret.sh` (jamais sur GitHub)
- Déploiement automatique par cronjob (`deploy.sh`, `setup-cronjob.sh`, `install.sh`, `INSTALL.md`)
- Tests unitaires (`python3 -m unittest discover -s tests`)

### Modifié
- Spotify abandonné (compte requis, extraits de 30 secondes seulement)
- Comparaison de titres via `difflib` (plus de dépendance `fuzzywuzzy`)

### Corrigé
- Les messages de log n'apparaissaient pas à l'écran
- Version `ffmpeg-python` inexistante dans `requirements.txt`

## [0.1.0] - 2024-10-05

### Added
- Initial project structure and setup
- Main application entry point with CLI interface
- Configuration system (JSON-based)
- Base source abstraction for theme providers
- AnimeThemes source skeleton
- MIT License
