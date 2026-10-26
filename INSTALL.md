# 🚀 Installation et déploiement de MouFlopening

Interface web sur le port **8001** (MouFlanimeXer : 5000, MouFloster : 8000).

Ce fichier est la référence : si le serveur disparaît, tout ce qu'il faut pour reconstruire à l'identique est dans ce dépôt.

Convention commune à **toutes** les applications du compte (MouFlanimeXer, MouFloster, MouFlopening, et les suivantes) : un dossier `/opt/<nom>`, un service systemd du même nom, et une mise à jour automatique par **cronjob** (jamais de webhook). L'appli marche aussi installée ailleurs que dans `/opt`.

## Installation sur une machine neuve

```bash
cd /opt
git clone https://github.com/mouflo/MouFlopening.git mouflopening
cd mouflopening
bash install.sh
```

`install.sh` installe les paquets du système (python3-venv, pip, git, curl, cron, ffmpeg), l'environnement Python, `config.json`, le service systemd (adapté au dossier choisi) et la mise à jour automatique (il demande sa fréquence). L'identifiant de connexion peut être créé pendant l'installation, ou à la **première ouverture de la page depuis le réseau local** (jamais à travers Internet ou un proxy).

Le dépôt doit pouvoir faire `git pull` sans mot de passe : le jeton GitHub (fine-grained, lecture seule sur ce dépôt) est placé dans l'URL du remote :

```bash
git remote set-url origin https://<TOKEN>@github.com/mouflo/MouFlopening.git
```

## Mises à jour automatiques

`setup-cronjob.sh [nuit|heure|minute|jamais]` (lancé par `install.sh`) **ajoute** une ligne à la crontab root, sans jamais remplacer les lignes des autres applications, par exemple chaque nuit à 5 h :

```
0 5 * * * bash /opt/mouflopening/deploy.sh >> /var/log/mouflopening-cron.log 2>&1
```

À chaque passage, `deploy.sh` compare le commit local à GitHub. S'il y a du nouveau : `git reset --hard`, réinstallation des dépendances si `requirements.txt` a changé, puis redémarrage du service s'il est actif.

## Vérifier

```bash
crontab -l
tail -f /var/log/mouflopening-deploy.log
tail -f /var/log/mouflopening-cron.log
```

## Fichiers de déploiement (tous dans ce dépôt)

- `deploy.sh` : script lancé par cron
- `setup-cronjob.sh` : installe la ligne cron (idempotent)
- `install.sh` : installation complète
- `mouflopening.service` : service systemd (source de vérité, copié dans `/etc/systemd/system/`)



## Connexion et clé Emby (rien à retaper)

Au premier déploiement, `deploy.sh` **reprend l'identifiant, le mot de passe (haché) et la clé Emby de MouFloster** installé à côté
(`<dossier des applis>/moufloster/data/secrets.env`), uniquement pour les clés absentes. Même compte sur les deux outils.
Ensuite, ⚙️ Réglages → Connexions → 🔗 Applis voisines → « 📥 Reprendre les réglages de » copie Emby, TheMovieDB ou Telegram d'une autre appli MouFl du même serveur.

Pour définir d'autres identifiants :
```bash
bash /opt/mouflopening/set-login.sh
bash /opt/mouflopening/set-secret.sh EMBY_API_KEY "clé"
```
Ils sont stockés dans `data/secrets.env` (ignoré par Git, jamais publié).

## Accès depuis internet

Comme les autres applications : Nginx Proxy Manager → `mouflopening.exemple.fr` vers `http://<ip-du-serveur>:8001`.

## Journal

La fenêtre « 🩺 Journal » de l'interface affiche un rapport copiable (clés masquées). Fichiers :
```bash
journalctl -u mouflopening -f
tail -f /var/log/mouflopening-deploy.log
```

## Précaution sur deploy.sh

`deploy.sh` se remplace lui-même pendant qu'il tourne (`git reset`). **Ne jamais modifier les lignes situées avant
`git reset`** : tout ce qui change se met après.

## Lot de nuit et Telegram (facultatif)

Sur la page, ouvre « 🌙 Lot de nuit & compte rendu Telegram » : coche l'option, choisis l'heure, colle le jeton de ton bot (obtenu auprès de @BotFather) et l'identifiant de ta discussion, puis « Enregistrer ». Un message de test arrive sur Telegram. Écris d'abord un message à ton bot, sinon Telegram refusera de t'en envoyer. Le jeton reste dans `data/secrets.env`, jamais sur GitHub.
