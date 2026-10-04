#!/bin/bash
# Installation de MouFlopening sur Proxmox (à lancer une fois après le clone)

set -e
REPO_DIR="/opt/mouflopening"
cd "$REPO_DIR"

chmod +x deploy.sh setup-cronjob.sh

if [ ! -d venv ]; then
    python3 -m venv venv
    ./venv/bin/pip install -q -r requirements.txt
fi

[ -f config.json ] || cp config.example.json config.json

# Le service systemd est installé mais PAS démarré : l'appli est encore un outil en ligne de commande.
cp mouflopening.service /etc/systemd/system/mouflopening.service
systemctl daemon-reload

bash setup-cronjob.sh

echo "✅ Installation terminée. Pense à renseigner config.json (clé API Emby...)."
