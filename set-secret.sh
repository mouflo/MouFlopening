#!/bin/bash
# Enregistre un secret localement (jamais sur GitHub). Exemple :
#   bash /opt/mouflopening/set-secret.sh EMBY_API_KEY "ta-clé"
set -e
[ $# -eq 2 ] || { echo "Usage : bash set-secret.sh NOM \"valeur\""; exit 1; }
DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$DIR/data"
FILE="$DIR/data/secrets.env"
touch "$FILE"; chmod 600 "$FILE"
grep -v "^$1=" "$FILE" > "$FILE.tmp" || true
echo "$1=\"$2\"" >> "$FILE.tmp"
mv "$FILE.tmp" "$FILE"; chmod 600 "$FILE"
echo "✅ $1 enregistré dans $FILE"
