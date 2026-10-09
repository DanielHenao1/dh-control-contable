#!/usr/bin/env bash
# Copia diaria cifrada (regla 3-2-1): base de datos + archivos cargados.
# Requiere en /opt/control/.env: BACKUP_PASSPHRASE y (para copia fuera del servidor) BACKUP_S3_BUCKET,
# BACKUP_S3_ENDPOINT, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${BACKUP_PASSPHRASE:?Falta BACKUP_PASSPHRASE}"
FECHA=$(date +%Y%m%d-%H%M%S)
DESTINO=/var/backups/control
mkdir -p "$DESTINO"
ARCHIVO="$DESTINO/control-$FECHA.tar.gz.gpg"

docker compose exec -T db pg_dump -U control -d control --format=custom > "/tmp/control-$FECHA.dump"
docker compose cp web:/app/media "/tmp/media-$FECHA" >/dev/null
tar -C /tmp -czf - "control-$FECHA.dump" "media-$FECHA" \
  | gpg --batch --yes --pinentry-mode loopback --symmetric --cipher-algo AES256 --passphrase "$BACKUP_PASSPHRASE" -o "$ARCHIVO"
rm -rf "/tmp/control-$FECHA.dump" "/tmp/media-$FECHA"

if [[ -n "${BACKUP_S3_BUCKET:-}" ]]; then
  aws s3 cp "$ARCHIVO" "s3://$BACKUP_S3_BUCKET/" ${BACKUP_S3_ENDPOINT:+--endpoint-url "$BACKUP_S3_ENDPOINT"}
  echo "Copia enviada fuera del servidor."
else
  echo "AVISO: sin BACKUP_S3_BUCKET la copia queda solo en este servidor (no cumple 3-2-1)." >&2
fi
# conserva 14 días en el servidor
find "$DESTINO" -name 'control-*.gpg' -mtime +14 -delete
echo "Copia lista: $ARCHIVO"
