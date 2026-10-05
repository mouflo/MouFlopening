#!/bin/bash
# Installation de MouFlopening sur Proxmox (à lancer une fois après le clone)

set -e
REPO_DIR="/opt/mouflopening"
cd "$REPO_DIR"

chmod +x deploy.sh setup-cronjob.sh

[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt

[ -f config.json ] || cp config.example.json config.json

cp mouflopening.service /etc/systemd/system/mouflopening.service
systemctl daemon-reload
systemctl enable mouflopening
systemctl restart mouflopening

bash setup-cronjob.sh

echo "✅ Installation terminée : http://<ip-du-serveur>:8001"
echo "Identifiant et clé Emby : repris de MouFloster au premier déploiement (sinon : bash set-login.sh puis bash set-secret.sh EMBY_API_KEY \"clé\")."
