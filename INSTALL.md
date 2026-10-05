# 🚀 Installation et déploiement de MouFlopening

Interface web sur le port **8001** (MouFlanimeXer : 5000, MouFloster : 8000).

Ce fichier est la référence : si le serveur disparaît, tout ce qu'il faut pour reconstruire à l'identique est dans ce dépôt.

Convention commune à **toutes** les applications du compte (MouFlanimeXer, MouFloster, MouFlopening, et les suivantes) : un dossier `/opt/<nom>`, un service systemd du même nom, et une mise à jour automatique par **cronjob** chaque minute (jamais de webhook).

## Installation sur une machine neuve

```bash
cd /opt
git clone https://github.com/mouflo/MouFlopening.git mouflopening
cd mouflopening
bash install.sh
```

Le dépôt doit pouvoir faire `git pull` sans mot de passe : le jeton GitHub (fine-grained, lecture seule sur ce dépôt) est placé dans l'URL du remote :

```bash
git remote set-url origin https://<TOKEN>@github.com/mouflo/MouFlopening.git
```

## Mises à jour automatiques

`setup-cronjob.sh` (lancé par `install.sh`) **ajoute** cette ligne à la crontab root, sans jamais remplacer les lignes des autres applications :

```
*/1 * * * * bash /opt/mouflopening/deploy.sh >> /var/log/mouflopening-cron.log 2>&1
```

Chaque minute, `deploy.sh` compare le commit local à GitHub. S'il y a du nouveau : `git reset --hard`, réinstallation des dépendances si `requirements.txt` a changé, puis redémarrage du service s'il est actif.

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

Au premier déploiement, `deploy.sh` **reprend l'identifiant, le mot de passe (haché) et la clé Emby de MouFloster**
(`/opt/moufloster/data/secrets.env`), uniquement pour les clés absentes. Même compte sur les deux outils.

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
