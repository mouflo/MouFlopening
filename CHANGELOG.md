# Changelog

## [0.11.0] - 2026-10-05

### Ajouté
- Nouvelle source pour les films et les séries : **ThemerrDB** (https://github.com/LizardByte/ThemerrDB, licence BSD-3-Clause), une base communautaire qui associe chaque film ou série (identifiant TheMovieDB) à la bonne vidéo YouTube de son thème, validée par des humains. Le thème proposé apparaît en tête de la liste, marqué « ★ », avant les résultats de la recherche YouTube ; il est aussi essayé en premier par le téléchargement automatique
- Nécessite la clé TheMovieDB (reprise de MouFloster ou saisie avec le bouton « Clé TMDB »). Sans clé ou si la base n'a rien pour un titre, la recherche YouTube habituelle continue seule

## [0.10.0] - 2026-10-05

### Amélioré
- La date de mise en ligne compte dans la recherche YouTube : avec l'année du dossier (« Titre (2025) »), une vidéo mise en ligne plus d'un an avant la sortie du film est fortement déclassée (sans rapport possible). L'année de mise en ligne s'affiche à côté de la durée dans chaque résultat
- L'année du dossier est aussi ajoutée à deux des recherches (« <titre> 2025 theme »), et prise en compte par le téléchargement automatique

## [0.9.2] - 2026-10-05

### Corrigé
- « This video is not available » alors que la vidéo marche dans le navigateur : YouTube refuse certains téléchargements depuis un serveur. L'appli déclenche maintenant la mise à jour de yt-dlp pour ce message aussi, puis réessaie avec d'autres « profils » de lecteur YouTube (tv, safari, mobile…) avant d'abandonner
- Le message d'échec ne prétend plus que la vidéo est retirée : il dit que YouTube refuse depuis le serveur ; la version de yt-dlp est inscrite dans le Journal pour le diagnostic

## [0.9.1] - 2026-10-05

### Corrigé
- Un téléchargement raté ne fait plus perdre le thème en place : le nouveau est d'abord reçu à côté, et l'ancien n'est mis de côté qu'une fois le nouveau bien enregistré (avant, l'ancien était déjà déplacé quand le téléchargement échouait)
- Message clair quand YouTube refuse une vidéo (« cette vidéo n'est plus disponible… choisis-en une autre », connexion demandée, vidéo trop longue, refus 403) au lieu de « voir le Journal »

## [0.9.0] - 2026-10-05

### Ajouté
- Titre original retrouvé sur Internet (TheMovieDB) quand Emby ne connaît pas le titre : cas des dossiers vides créés par Radarr pour un film pas encore téléchargé. On cherche avec le titre du dossier et l'année ; le thème peut ainsi être préparé « en prévision ». Emby reste consulté en premier
- Même repli dans le téléchargement automatique : si rien n'est trouvé sous le titre du dossier, le titre original est essayé
- Bouton « 🔑 Clé TMDB » (saisie et test de la clé depuis la page). Sans clé enregistrée ici, la clé de MouFloster est reprise automatiquement (lue sur le serveur, jamais copiée ni affichée)

## [0.8.1] - 2026-10-05

### Amélioré
- Le titre original (d'après Emby) est maintenant cherché en premier
- Quand le titre original ne peut pas être utilisé, la page dit pourquoi (titre introuvable dans Emby, ou pas de titre original renseigné dans Emby) et le Journal garde le détail (« nom Emby », « titre original »)

## [0.8.0] - 2026-10-05

### Amélioré
- Recherche YouTube beaucoup plus large, comme une recherche à la main : six formulations lancées en parallèle (« <titre> theme », « main theme », « soundtrack », « OST », « bande originale »… ; pour une série : « theme song », « intro », « générique »…), résultats fusionnés sans doublon et classés, jusqu'à 10 propositions par titre (12 avec le titre original)
- Recherche plus rapide : liste légère (titre, durée, chaîne) au lieu de l'analyse complète de chaque vidéo

## [0.7.3] - 2026-10-05

### Corrigé
- Écoute : lancer un thème arrête et ferme celui qui jouait déjà (lecteur YouTube comme lecteur audio d'AnimeThemes). Un seul thème à la fois

## [0.7.2] - 2026-10-05

### Corrigé
- Téléchargement YouTube refusé (« HTTP Error 403: Forbidden ») : l'outil de téléchargement (yt-dlp) devient vite trop ancien quand YouTube change. Dans ce cas l'appli le met maintenant à jour toute seule (au plus une fois toutes les 6 h) puis réessaie

## [0.7.1] - 2026-10-05

### Corrigé
- Les listes s'adaptent à l'onglet : « Film sans thème / Tous / Avec thème » pour les films (plus de choix « saison »), « Anime sans thème » pour les animes, « Série sans thème » pour les séries ; le compteur indique « animes », « séries » ou « films »

## [0.7.0] - 2026-10-05

### Ajouté
- Recherche sous le titre original : une case « Chercher aussi sous le titre original (d'après Emby) », cochée par défaut, lance la recherche avec le titre du dossier ET le titre original connu d'Emby, et fusionne les résultats (les titres essayés sont indiqués au-dessus de la liste). Le choix de la case est mémorisé dans le navigateur

### Supprimé
- Le bouton « ⚡ Automatique » de la fiche d'un titre (contrôle manuel : on choisit soi-même avec « Utiliser »). Le lot automatique de tout un onglet reste disponible

## [0.6.4] - 2026-10-05

### Corrigé
- Écoute YouTube : le lecteur intégré affichait « Erreur 153 » car l'appli n'envoyait aucune information de provenance à YouTube. Le lecteur est de nouveau autorisé à démarrer (la provenance n'est envoyée que par une connexion HTTPS)

## [0.6.3] - 2026-10-05

### Corrigé
- Barre de progression : les films n'apparaissent plus comme « série » (libellé « film » pour l'onglet Films, et plus de saisons cherchées pour un film)
- Recherche automatique de tout un onglet : le type de l'onglet (anime, série, film) n'était plus transmis, donc YouTube était utilisé même pour les animes. Chaque onglet utilise de nouveau sa bonne source (AnimeThemes pour les animes)

## [0.6.2] - 2026-10-05

### Amélioré
- Normalisation : l'avancement est enregistré au fil de l'eau (toutes les 20 thèmes). Si l'appli redémarre en plein traitement (mise à jour automatique), la relance ne refait pas ce qui était déjà fait
- Les thèmes déjà au bon niveau sont aussi mémorisés ; les restes de copie interrompue (`*.partiel`) sont nettoyés

## [0.6.1] - 2026-10-05

### Corrigé
- La normalisation s'arrêtait sur le NAS (« Operation not permitted » : dates des fichiers non modifiables). Les copies et déplacements passent maintenant par un mode tolérant (copie à côté puis renommage), et un fichier en erreur n'arrête plus tout le lot

## [0.6.0] - 2026-10-05

### Modifié
- **Trois onglets seulement : Animes, Séries, Films.** Les dossiers du même type sont regroupés (Films HD + Films 4K dans l'onglet Films, avec le dossier d'origine affiché sur chaque ligne). Les dossiers dont le nom n'évoque aucun de ces types sont ignorés (liste dans le Journal) ; on peut les ajouter à la main dans `config.json` (`library.categories`, avec `kind` et `path` ou `paths`)
- **Les anciens thèmes sont mis de côté dans `/mnt/mouflosyno/MouFlopening/Anciens thèmes`** (réglable : `themes.backup_dir`), plus dans `data/`. Les sauvegardes déjà faites dans `data/themes-backup` y sont déplacées automatiquement. Si le partage est inaccessible, repli provisoire sur `data/`
- Actualisation Emby : distingue un même film présent en HD et en 4K

## [0.5.1] - 2026-10-05

### Ajouté
- Bouton **« 🔑 Clé Emby »** : on colle la clé dans la page, elle est testée auprès d'Emby puis enregistrée dans `data/secrets.env` (plus besoin de ligne de commande)

## [0.5.0] - 2026-10-05

### Ajouté
- **Onglets par médiathèque** (Anime, Séries, Films…) : chaque sous-dossier de `/mnt/mouflosyno/Emby-Media` devient un onglet, le type est deviné d'après le nom (Manga/Anime → anime, Films → films, le reste → séries). Réglable dans `config.json` (`library.auto_parent`, `library.categories` avec `name`, `path`, `kind`)
- **Source YouTube** (yt-dlp) pour les séries et les films : résultats classés, écoute dans la page, téléchargement de l'audio converti en MP3 normalisé à 89 dB. AnimeThemes reste la source des animes
- **Films** : un dossier par film, un `theme.mp3` dedans ; actualisation Emby ciblée du film
- Le lot automatique et les compteurs s'appliquent à l'onglet affiché ; l'onglet choisi est mémorisé

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
