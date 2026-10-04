#!/bin/bash
# Installe la cronjob de mise à jour automatique (idempotent).
# AJOUTE la ligne à la crontab root, ne remplace JAMAIS les lignes existantes (MouFloster, MouFlanimeXer...).

set -e

REPO_DIR="/opt/mouflopening"
DEPLOY_SCRIPT="$REPO_DIR/deploy.sh"
CRON_LOG="/var/log/mouflopening-cron.log"

[ -d "$REPO_DIR" ] || { echo "❌ $REPO_DIR introuvable"; exit 1; }

touch "$CRON_LOG"
chmod 666 "$CRON_LOG"

CRON_ENTRY="*/1 * * * * bash $DEPLOY_SCRIPT >> $CRON_LOG 2>&1"

if crontab -l 2>/dev/null | grep -qF "$DEPLOY_SCRIPT"; then
    echo "✅ La cronjob est déjà configurée"
else
    (crontab -l 2>/dev/null || true; echo "$CRON_ENTRY") | crontab -
    echo "✅ Cronjob ajoutée (toutes les minutes)"
fi

echo "Crontab actuelle :"
crontab -l
