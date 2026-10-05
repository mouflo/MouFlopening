# Changelog

## [0.23.0] - 2026-10-05

### Ajouté
- Éditeur audio « ✂️ » : courbe du son, zoom (boutons ➕ ➖, pincement au doigt, molette), défilement, poignées verte (début) et rouge (fin) pour couper les parties indésirables (intro de chaîne…), boutons « Début ici » / « Fin ici » pour une coupe précise à l'oreille, écoute de la partie gardée avec aperçu des fondus, fondu d'entrée et de sortie réglables. Pensé pour le téléphone
- Accessible depuis : « ✂️ Éditer ce thème » (thème actuel), le bouton ✂️ à côté de « Utiliser » sur chaque proposition, et « ✂️ Éditer d'abord » dans « Utiliser mon propre thème » (lien ou fichier)
- À l'enregistrement le thème est converti en MP3 et remis au volume habituel ; l'ancien thème est mis de côté (pas supprimé). Les copies de travail sont effacées au bout de 6 h

## [0.22.0] - 2026-10-05

### Ajouté
- « 🎵 Utiliser mon propre thème » sur chaque série, saison ou film : coller un lien (YouTube, ou autre site pris en charge par yt-dlp comme SoundCloud) ou envoyer un fichier audio de son ordinateur (mp3, m4a, flac, ogg, wav… 150 Mo maximum). Le thème est converti en MP3, mis au même volume que les autres, et remplace l'actuel (l'ancien est mis de côté, pas supprimé). Pratique pour choisir le thème d'un héros plutôt qu'un générique de saison
- Les liens vers le réseau local ou une adresse privée sont refusés (l'appli ne sert pas à atteindre le réseau de la maison)

## [0.21.1] - 2026-10-05

### Corrigé
- Une saison (y compris la saison 1) qui aurait exactement le même thème que la série n'est plus enregistrée, et le contrôle « Doublons de saisons » la signale aussi : une saison sans fichier propre reprend la musique de la série, alors qu'un fichier identique mais distinct peut faire repartir la musique en entrant dans la saison

## [0.21.0] - 2026-10-05

### Ajouté
- Réglages · Dossiers : chaque sous-dossier du dossier des médiathèques est proposé avec une case à cocher et un menu « Films / Séries / Animes » (le type est deviné d'après le nom, modifiable ; un dossier au nom inconnu s'active en choisissant son type)
- Réglages · Dossiers : « ➕ Ajouter un dossier » pour un dossier situé ailleurs, et explorateur « 📂 Parcourir » pour naviguer dans les dossiers du serveur au lieu de taper un chemin (il ne montre que des dossiers et ne modifie rien)
- Contrôle « 🔎 Doublons de saisons » : repère les saisons qui ont exactement le même thème que la série (saison 1 exceptée) ou qu'une autre saison, et permet de les remettre dans « sans thème » (les fichiers vont dans le dossier des anciens thèmes, rien n'est supprimé)
- Réglages · Cookies YouTube (facultatif) : coller un fichier cookies.txt pour aider quand YouTube demande une connexion ou refuse un téléchargement. Gardé sur le serveur (droits 600), jamais affiché ni écrit dans le Journal
- Réglages · Lot de nuit : option « Remplir aussi les saisons des animes »

### Corrigé
- Animes : une saison 2 ou plus ne reçoit plus automatiquement le même thème que la série ou qu'une autre saison (cas où AnimeThemes n'a pas de fiche propre à la saison et où la recherche retombait sur celle de la saison 1) : elle reste « sans thème » pour un choix manuel. L'origine de chaque thème est mémorisée (data/theme_sources.json)

## [0.20.0] - 2026-10-05

### Ajouté
- Page « ⚙️ Réglages » (bouton en haut de la page, à la place de « Clé Emby » et « Clé TMDB ») qui regroupe tout : adresse et clé API d'Emby, clé TheMovieDB, dossier des médiathèques, dossier des anciens thèmes, lot de nuit et bot Telegram. Les onglets trouvés dans le dossier choisi sont affichés
- Changer les dossiers redémarre l'appli toute seule (quelques secondes) pour les relire ; l'adresse d'Emby, les clés et Telegram sont pris en compte tout de suite
- Rien n'est enregistré si le dossier est introuvable sur le serveur ou si Telegram refuse le jeton

### Modifié
- Le panneau « Lot de nuit » quitte la page d'accueil pour la page Réglages

## [0.19.0] - 2026-10-05

### Ajouté
- Lot de nuit : chaque nuit à l'heure choisie (3 h par défaut), l'appli cherche les thèmes manquants de tous les onglets (mêmes règles que le lot manuel) puis envoie un compte rendu illustré d'emojis sur Telegram. Aucun message n'est envoyé quand rien de nouveau n'a été trouvé
- Panneau « 🌙 Lot de nuit & compte rendu Telegram » sur la page : activer, choisir l'heure, régler le bot Telegram (jeton + identifiant de discussion, vérifiés par un message de test), « Lancer maintenant ». Le jeton est gardé dans data/secrets.env, jamais sur GitHub ni renvoyé à la page ; à défaut, la config Telegram de MouFlanimeXer est reprise si elle existe sur la même machine

## [0.18.0] - 2026-10-05

### Ajouté
- Mise à jour automatique de yt-dlp : au démarrage de l'appli puis chaque jour (en attendant qu'aucun lot ne tourne). YouTube change souvent et yt-dlp suit : l'appli reste à jour sans intervention

### Amélioré
- Un `theme.mp3` vide ou tronqué (moins de 8 Ko : reste d'un ancien plugin ou d'un téléchargement cassé) compte maintenant comme « sans thème » : il réapparaît dans la liste, est pris en compte par le lot automatique, et l'ancien fichier est mis de côté au remplacement

## [0.17.1] - 2026-10-05

### Amélioré
- Quand un traitement automatique est terminé, un bouton « ✕ Fermer » apparaît dans la fenêtre « Dernier traitement » : il retire la fenêtre et la barre verte « Terminé », qui ne reviennent pas au rechargement de la page (elles réapparaissent au prochain traitement)

## [0.17.0] - 2026-10-05

### Amélioré
- « ⏭ Mettre de côté » pendant une recherche l'arrête tout de suite (la page n'attend plus la fin, et le serveur cesse de chercher sur YouTube à l'étape suivante) puis met le titre de côté

## [0.16.5] - 2026-10-05

### Corrigé
- « Introuvable dans Emby (pas encore scanné ?) » s'affichait à tort pour des films pourtant présents (Destination finale 4, Me Time - Enfin seul !, OSS 117, Terminator, Troie…) : la recherche texte d'Emby les ratait. L'application charge maintenant la liste complète des films/séries d'Emby (gardée 2 minutes) et retrouve chacun par le nom exact de son dossier (accents et majuscules ignorés, « Films HD » / « Films 4K » distingués). L'ancienne recherche reste en secours
- Conséquence : l'identifiant TheMovieDB et le titre original d'Emby sont retrouvés, et Emby est bien rafraîchi après l'enregistrement d'un thème

## [0.16.4] - 2026-10-05

### Amélioré
- Si le thème de la communauté (★) ne peut pas être téléchargé (vidéo bloquée par YouTube pour droits d'auteur…), la page lance tout de suite la recherche YouTube normale, sans cette vidéo, pour proposer d'autres choix au lieu de rester bloqué

## [0.16.3] - 2026-10-05

### Amélioré
- Les thèmes choisis par la communauté (ThemerrDB) peuvent maintenant durer jusqu'à 25 minutes (limite de 10 minutes pour les autres vidéos YouTube) : plusieurs étaient refusés « trop longue » à tort
- Les refus de YouTube sont expliqués précisément : durée réelle de la vidéo quand elle est trop longue, ou « YouTube bloque cette vidéo (droits d'auteur / pays) » quand le titre est bloqué pour cause de contenu protégé (cas de Man of Steel)

## [0.16.2] - 2026-10-05

### Corrigé
- Quand une mise à jour redémarre l'appli au milieu d'un téléchargement, le fichier temporaire « theme.nouveau.partiel » restait dans le dossier du film. Il est maintenant retiré automatiquement au démarrage (s'il date de plus de 10 minutes)

## [0.16.1] - 2026-10-05

### Amélioré
- Quand ThemerrDB ne donne rien, la progression dit pourquoi et avec quel identifiant TheMovieDB la base a été interrogée (pour repérer une mauvaise correspondance de titre)

## [0.16.0] - 2026-10-05

### Amélioré
- La recherche du thème validé par la communauté (ThemerrDB) se fait maintenant d'abord avec le **titre original** : l'identifiant TheMovieDB est pris chez Emby quand il le connaît (correspondance exacte, rien à deviner), sinon retrouvé d'après le titre original (la plupart des films sont américains et la base les connaît sous ce nom), et en dernier recours d'après le titre du dossier. Valable pour la recherche à la main comme pour le téléchargement de tous les thèmes manquants (qui ne prend toujours que les thèmes validés, sans aucun choix sur YouTube)
- Les étapes de cette recherche s'affichent en direct dans la progression

## [0.15.1] - 2026-10-05

### Amélioré
- Le détail du traitement en lot (téléchargement ou normalisation) est maintenant une petite fenêtre de 4-5 lignes, toujours visible sous la barre de progression, qui défile toute seule : la ligne en cours (⏳) est en bas, en gras, et les précédentes remontent. Plus besoin de l'ouvrir ni de défiler la page. Elle reste collée en haut de l'écran quand on descend dans la page, et un bouton « Tout voir » l'agrandit pour relire tout l'historique

## [0.15.0] - 2026-10-05

### Ajouté
- **Supprimer un thème existant**, avec double validation : le bouton « 🗑 Supprimer ce thème » (sous le lecteur du thème actuel) demande d'abord « Continuer », puis une « Dernière validation ». Le serveur refuse aussi toute suppression sans cette double validation. Le fichier n'est pas détruit : il est mis de côté dans le dossier des anciens thèmes, et Emby est prévenu

## [0.14.0] - 2026-10-05

### Corrigé
- **Films et séries : le téléchargement de tous les thèmes manquants ne prend plus que les thèmes validés par la communauté (ThemerrDB).** Avant, il choisissait tout seul la première vidéo YouTube à peu près ressemblante, et validait n'importe quoi. Maintenant, si ThemerrDB ne connaît pas le titre, on passe directement au suivant (le titre reste dans « sans thème » pour une recherche à la main). Les animes continuent d'utiliser AnimeThemes
- Pour les films et séries, le lot ne traite plus les saisons (ThemerrDB ne connaît que le film ou la série entière)

## [0.13.1] - 2026-10-05

### Amélioré
- Quand ThemerrDB propose un thème (validé par la communauté), la recherche s'arrête là : plus de recherche YouTube ni de recherche du titre original, donc le résultat arrive beaucoup plus vite. Un bouton « Chercher aussi sur YouTube » (ou le bouton « Chercher ») permet de voir d'autres propositions

## [0.13.0] - 2026-10-05

### Ajouté
- **Mis de côté** : quand une recherche ne trouve rien, le titre quitte automatiquement la liste « sans thème » (il est marqué « rien trouvé ») : plus besoin de refaire défiler toute la liste pour retrouver ceux qu'on n'a pas encore cherchés. Un nouveau filtre « Recherché sans résultat » les regroupe, et un compteur « mis de côté » apparaît en haut
- Boutons « ⏭ Mettre de côté » (à la main) et « ↩ Remettre dans la liste » sur la fiche d'un titre. Un titre mis de côté n'est plus recherché tout seul quand on le sélectionne
- Le téléchargement de tous les thèmes manquants laisse de côté les titres déjà recherchés sans résultat, et y range ceux qu'il ne trouve pas. Dès qu'un thème est enregistré, le titre sort de cette catégorie

## [0.12.2] - 2026-10-05

### Corrigé
- Sur téléphone, l'étape en cours de la recherche est maintenant placée à environ un tiers de la hauteur de l'écran (la page laisse la place nécessaire) et reste visible quand de nouvelles étapes arrivent

## [0.12.1] - 2026-10-05

### Corrigé
- Sur téléphone, la progression en direct (recherche et « Utiliser ») est maintenant ramenée automatiquement à l'écran : plus besoin de faire défiler la page vers le bas pour la voir

## [0.12.0] - 2026-10-05

### Ajouté
- **Progression en direct** pendant la recherche : la page affiche chaque étape au fur et à mesure (titre original, ThemerrDB trouvé ou non, recherche YouTube, vérification des dates, classement) avec un compteur de secondes, au lieu d'un « Recherche sur YouTube… » figé
- **Progression en direct** quand on clique sur « Utiliser » : connexion à YouTube, pourcentage de téléchargement, nouvel essai si YouTube refuse, conversion et réglage du volume, mise en place du thème, mise à jour d'Emby

## [0.11.3] - 2026-10-05

### Corrigé
- Recherche d'un film ou d'une série : l'erreur « 'Urllib3PercentREOverride' object has no attribute 'sub' » est corrigée. Elle venait d'une incompatibilité entre yt-dlp et la bibliothèque de requêtes (urllib3) : une fois yt-dlp chargé, plus aucune requête vers TheMovieDB, ThemerrDB ou Emby ne passait. La pièce abîmée est remise en état avant chaque requête

## [0.11.2] - 2026-10-05

### Amélioré
- Le journal indique maintenant ce qui se passe pour ThemerrDB et TheMovieDB (titre trouvé, identifiant, ou raison de l'échec), pour comprendre pourquoi une recherche ne donne rien
- Quand YouTube refuse un téléchargement, le profil de connexion qui a fini par marcher est mémorisé et réessayé en premier la fois suivante
- Le rapport de diagnostic indique si la clé TheMovieDB est définie (4 derniers caractères seulement)

## [0.11.1] - 2026-10-05

### Corrigé
- Le numéro de version affiché en haut de la page (« v0.11.1 (abc1234) ») correspond maintenant à celui de ce journal des modifications. Avant, la page comptait les mises à jour (« v0.2.33 ») et ne correspondait à aucun numéro annoncé

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
