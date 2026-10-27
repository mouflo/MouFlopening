# MouFlopening 🎬🎵

[![Licence : MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**Des thèmes musicaux pour ta médiathèque Emby** : une appli web qui trouve, télécharge et met en place le fichier `theme.mp3` de chaque film, série et anime, au bon niveau sonore.

## 📸 Aperçu

*Captures avec des données de démonstration.*

**La liste des films, séries et animes, avec ceux qui n'ont pas encore de thème**

![La liste des films, séries et animes, avec ceux qui n'ont pas encore de thème](docs/screenshots/liste.png)

**Les propositions pour un titre : la sélection ★ de la base ThemerrDB en tête, puis les résultats YouTube**

![Les propositions pour un titre : la sélection ★ de la base ThemerrDB en tête, puis les résultats YouTube](docs/screenshots/recherche.png)

**La recherche annonce chaque étape en direct (titre original, ThemerrDB, YouTube…)**

![La recherche annonce chaque étape en direct (titre original, ThemerrDB, YouTube…)](docs/screenshots/progression.png)

**La page ⚙️ Réglages → Connexions : Emby, TheMovieDB, MouFloster, applis voisines, cookies YouTube**

![La page Réglages](docs/screenshots/reglages.png)

**L'éditeur audio (couper, zoomer, fondus), pensé pour le téléphone**

![L'éditeur audio](docs/screenshots/editeur.png)

**Les anciens thèmes d'un titre : écouter, restaurer, annuler le dernier remplacement**

![Les anciens thèmes d'un titre](docs/screenshots/anciens.png)

**Sur téléphone : la fiche d'un titre, avec « 🖼️ Poster dans MouFloster », « ⏭ Titre suivant » et l'enchaînement**

![Sur téléphone](docs/screenshots/mobile.png)

## 👥 Comptes copains (1.0)
⚙️ Réglages → Comptes → crée un compte : le copain arrive sur une page simple « 🎵 Trouver un générique ». Il récupère tes génériques déjà choisis (lecture seule) ou un générique validé par la communauté (ThemerrDB, AnimeThemes), jamais une vidéo YouTube choisie au hasard.

## ✨ Fonctionnalités

- 🎵 **Plusieurs sources** : AnimeThemes (génériques d'animes), ThemerrDB (thèmes validés par la communauté pour les films et séries) et YouTube
- ⚡ **Ouverture instantanée** : la liste de la médiathèque est gardée dans un index SQLite (`data/index.sqlite`), mis à jour seulement pour les titres dont le dossier a changé. Les onglets Animes / Séries / Films se recalculent tout seuls quand le NAS est monté après le démarrage.
- 🔎 **Recherche YouTube plus large** : douze à quatorze formulations (main theme, opening, theme song, générique…), les vidéos sans rapport avec le titre écartées, les reprises et compilations reléguées, et chaque proposition dit pourquoi elle est proposée.
- 🎯 **Recherche soignée** : titre original d'après Emby et TheMovieDB, vérification des saisons d'animes, jamais le même thème pour une série et sa saison 1
- 📚 **Traitement par lots** : télécharge d'un coup tous les thèmes manquants, avec progression en direct et possibilité d'arrêter
- 🌙 **Lot de nuit** : l'appli cherche toute seule les thèmes manquants à l'heure choisie, puis envoie un compte rendu sur Telegram seulement s'il y a du nouveau : titres arrivés dans Emby (générique posé cette nuit, déjà là ou à chercher, et poster à faire d'après MouFloster), thèmes ajoutés, et seulement les nouveaux titres sans thème (les autres tiennent en une ligne « toujours sans thème »). Un film ou une série absent de ThemerrDB n'est revérifié qu'une fois par semaine ; une panne de ThemerrDB ou de TheMovieDB est retentée la nuit suivante
- ⏭ **Enchaîner** : une fois le générique posé, l'appli peut passer toute seule au titre suivant de la liste (case « Enchaîner »), recherche déjà lancée ; « ⏭ Titre suivant » passe au suivant sans rien enregistrer
- 🖼️ **Avec MouFloster** : « 🖼️ Poster dans MouFloster » ouvre MouFloster sur le titre (et la saison) avec un lien pour revenir ; après l'envoi d'un poster dans MouFloster, MouFlopening cherche lui-même le générique validé du titre
- 🔗 **Applis voisines** : sur le même serveur, les applis MouFl se parlent directement (clé créée toute seule, rien à régler) ; ⚙️ Réglages → Connexions → « 📥 Reprendre les réglages de » copie Emby, TheMovieDB ou Telegram d'une autre appli au lieu de les retaper
- 🔊 **Volume homogène** : chaque thème est ramené au même niveau (89 dB par défaut, réglable)
- ✂️ **Éditeur audio** : coupe le début et la fin, zoom sur la courbe, fondus d'entrée et de sortie
- 🎶 **Ton propre thème** : colle un lien (YouTube ou autre) ou envoie un fichier audio
- 🔄 **Emby** : actualise seulement le titre concerné après chaque thème
- 🛟 **Rien n'est perdu** : l'ancien thème est mis de côté avant d'être remplacé, et on peut le réécouter et le **restaurer** d'un clic (« Annuler le dernier remplacement »)
- ✂️ **Coupe automatique** (option) : les thèmes trop longs sont coupés à la durée choisie, avec un fondu de sortie
- 🔁 **Titres mis de côté** : la raison et la date sont gardées, ils sont retentés automatiquement après N jours (réglable), ou tout de suite avec « Réessayer les mis de côté »
- 🛡️ **NAS vérifié avant chaque lot** : si le partage réseau n'est pas monté, rien n'est touché et Telegram prévient
- ⚙️ **Page Réglages** : adresse et clé d'Emby, clé TheMovieDB, volume, dossiers (avec explorateur), cookies YouTube, lot de nuit et Telegram, sans toucher à un fichier
- 🩺 **Journal et diagnostic** : un bouton pour copier l'état du serveur quand quelque chose ne va pas
- 📱 **Pensée pour le téléphone** (liste compressée : dix fois moins de données à chaque rechargement), mises à jour automatiques de yt-dlp
- 🧰 **Installable chez d'autres** : `install.sh` installe les paquets (python3-venv, ffmpeg…), le service et la mise à jour automatique (chaque nuit, chaque heure, chaque minute ou jamais) ; l'identifiant se crée à la première ouverture de la page depuis le réseau local ; aucune valeur propre à une maison par défaut

## 🚀 Installation

Tout est expliqué dans [`INSTALL.md`](INSTALL.md) : installation sur un conteneur Proxmox/LXC, mises à jour automatiques depuis GitHub (fréquence au choix) et reconstruction complète après une panne.

En bref :

```bash
cd /opt
git clone https://github.com/mouflo/MouFlopening.git mouflopening
cd mouflopening
bash install.sh
```

Ouvre ensuite `http://<adresse-du-serveur>:8001` depuis ton réseau local (l'identifiant se crée à la première ouverture), puis la page **⚙️ Réglages** pour indiquer Emby, la clé TheMovieDB et tes dossiers (ou les reprendre d'une appli MouFl voisine). Les clés restent sur ton serveur (`data/secrets.env`), jamais sur GitHub.

## 📖 Utilisation

1. Choisis l'onglet **Animes**, **Séries** ou **Films** : l'appli montre ce qui n'a pas encore de thème.
2. Clique sur un titre : les propositions arrivent (la sélection ★ de la communauté en tête), avec un bouton pour les écouter.
3. **Utiliser** pose le thème dans le dossier du titre. Le bouton ✂️ ouvre l'éditeur pour couper ou ajouter des fondus avant.
4. Pour tout faire d'un coup : **Télécharger tous les thèmes manquants**, ou active le **lot de nuit** dans les Réglages.

## 🤝 Dans la même famille

[MouFlanimeXer](https://github.com/mouflo/MouFlanimeXer) (remux d'animes) · [MouFloster](https://github.com/mouflo/MouFloster) (posters) : même style et même page Réglages.

## 📝 Licence

Ce projet est sous licence MIT (voir le fichier `LICENSE`) : tu peux le réutiliser, le modifier et le partager librement.
