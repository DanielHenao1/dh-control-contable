#!/usr/bin/env bash
# Restaura una copia cifrada en un entorno limpio (úsalo cada mes para probar la restauración).
# Uso: deploy/restore.sh /var/backups/control/control-YYYYmmdd-HHMMSS.tar.gz.gpg
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
ARCHIVO=${1:?Indica el archivo .gpg}
TMP=$(mktemp -d)
gpg --batch --yes --pinentry-mode loopback --decrypt --passphrase "$BACKUP_PASSPHRASE" "$ARCHIVO" | tar -C "$TMP" -xzf -
DUMP=$(ls "$TMP"/control-*.dump)
echo "Esto REEMPLAZA la base actual. Escribe SI para continuar:"; read -r R; [[ "$R" == "SI" ]] || exit 1
docker compose exec -T db pg_restore -U control -d control --clean --if-exists < "$DUMP"
docker compose cp "$TMP"/media-*/. web:/app/media
rm -rf "$TMP"
echo "Restauración completa. Verifica el ingreso y una carga reciente."
