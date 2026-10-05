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

# Identifiants et clé Emby : repris de MouFloster au premier déploiement (même compte, rien à retaper).
# Seules les clés absentes sont copiées ; les valeurs ne sont jamais écrites dans le journal.
SRC_SECRETS="/opt/moufloster/data/secrets.env"
DST_SECRETS="$REPO_DIR/data/secrets.env"
if [ -f "$SRC_SECRETS" ]; then
    mkdir -p "$REPO_DIR/data"
    touch "$DST_SECRETS"
    chmod 600 "$DST_SECRETS"
    for KEY in APP_USER APP_PASSWORD_HASH EMBY_API_KEY EMBY_URL; do
        grep -q "^$KEY=" "$DST_SECRETS" && continue
        LINE=$(grep "^$KEY=" "$SRC_SECRETS" | head -1)
        if [ -n "$LINE" ]; then
            printf '%s\n' "$LINE" >> "$DST_SECRETS"
            log "🔑 $KEY repris de MouFloster"
        fi
    done
fi

# Service systemd : le fichier du dépôt est la source de vérité
if ! cmp -s "$REPO_DIR/mouflopening.service" /etc/systemd/system/mouflopening.service; then
    cp "$REPO_DIR/mouflopening.service" /etc/systemd/system/mouflopening.service
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME" >/dev/null 2>&1
    log "📋 Service systemd mis à jour"
fi

# Redémarrer l'appli web
systemctl restart "$SERVICE_NAME"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "✅ Déploiement réussi, service redémarré"
else
    log "❌ Le service n'a pas pu démarrer (voir : journalctl -u $SERVICE_NAME -e)"
    exit 1
fi
