#!/bin/bash
# Déploiement automatique de MouFlopening (lancé par cron chaque minute)
# Même méthode que MouFloster et MouFlanimeXer : git fetch, reset si nouveau commit, redémarrage du service.

REPO_DIR="/opt/mouflopening"
LOG_FILE="/var/log/mouflopening-deploy.log"
SERVICE_NAME="mouflopening"

log() { echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

touch "$LOG_FILE"
cd "$REPO_DIR" || { log "❌ $REPO_DIR introuvable"; exit 1; }

OLD_COMMIT=$(git rev-parse HEAD)
git fetch origin -q
NEW_COMMIT=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master)

if [ "$OLD_COMMIT" = "$NEW_COMMIT" ]; then
    exit 0
fi

log "=== 🚀 Déploiement MouFlopening détecté ==="
log "Ancien commit: $OLD_COMMIT"
log "Nouveau commit: $NEW_COMMIT"

git reset --hard origin/main || git reset --hard origin/master

# config.json encore au stade « copie du modèle » (adresse Emby d'exemple) : on le régénère avec les bonnes valeurs par défaut
if [ -f config.json ] && grep -q "192.168.1.100" config.json; then
    cp config.example.json config.json
    log "⚙️  config.json mis à jour depuis le modèle"
fi

# Réinstaller les dépendances si requirements.txt a changé
if git diff "$OLD_COMMIT" HEAD -- requirements.txt | grep -q .; then
    log "📦 requirements.txt modifié, installation des dépendances..."
    if [ -d "./venv" ]; then
        ./venv/bin/python -m pip install -q -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
    else
        log "⚠️  venv introuvable, dépendances non installées"
    fi
fi

# Redémarrer le service seulement s'il est actif (l'appli est pour l'instant un outil en ligne de commande)
if systemctl is-active --quiet "$SERVICE_NAME"; then
    systemctl restart "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "✅ Déploiement réussi, service redémarré"
    else
        log "❌ Le service n'a pas pu redémarrer"
        exit 1
    fi
else
    log "✅ Code mis à jour (aucun service actif à redémarrer)"
fi
