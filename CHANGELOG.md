# Changelog

## [0.4.0] - 2026-10-05

### Ajouté
- Bouton **« Normaliser les thèmes existants à 89 dB »** : traite les thèmes MP3 déjà présents, sans rien refaire si déjà à 89 dB (registre `data/normalized.json`), sauvegarde de l'original dans `data/themes-backup`
- Reconnaissance de `theme.mp3/.flac/.wav/.ogg/.m4a…` et du sous-dossier `theme-music/` (comme Emby) ; l'ancien thème est sauvegardé avant tout remplacement
- Interface mobile adaptée (plus de débordement horizontal) ; liste et candidats se replient quand on choisit une série (▾ changer)
- Dossier **Specials / S0** géré comme une saison (un thème pour le dossier). Emby ne gère pas de thème par fichier : pour un thème par film, mettre chaque film dans son propre dossier

## [0.3.0] - 2026-10-05

### Ajouté
- **Normalisation à 89 dB** de chaque thème (référence ReplayGain, celle de MP3Gain), mesurée puis appliquée précisément pendant la conversion, avec un limiteur à -1 dBFS contre la saturation. Réglable : `audio.target_db` dans `config.json`
- **Thèmes de saison** : `theme.mp3` dans chaque dossier de saison (Season 1, Saison 02, S03, Specials), choix manuel par saison (onglets Série / Saison 1 / Saison 2…), actualisation Emby de la saison concernée
- Lot automatique : case « avec les saisons » (saison N cherchée sous « Titre Season N »)
- Filtre « Saison sans thème » et compteur de saisons dans la liste

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
- Premier déploiement du service web : relancé par un nouveau commit (l'ancien `deploy.sh` s'était remplacé en cours d'exécution et avait sauté l'installation du service)
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
