#!/usr/bin/env bash
# Entrega la última copia cifrada a un computador autorizado. Se usa como comando forzado en
# ~/.ssh/authorized_keys, así que esa llave SOLO puede ejecutar estas tres órdenes:
#   name   -> nombre del archivo más reciente
#   sha    -> huella SHA-256 del archivo más reciente
#   latest -> contenido del archivo más reciente (ya cifrado con BACKUP_PASSPHRASE)
set -euo pipefail
DIR=/var/backups/control
ULTIMA=$(ls -1t "$DIR"/control-*.tar.gz.gpg 2>/dev/null | head -1 || true)
[[ -n "$ULTIMA" ]] || { echo "No hay copias en $DIR" >&2; exit 1; }
case "${SSH_ORIGINAL_COMMAND:-}" in
  name) basename "$ULTIMA" ;;
  sha) sha256sum "$ULTIMA" | cut -d' ' -f1 ;;
  latest) cat "$ULTIMA" ;;
  *) echo "Orden no permitida" >&2; exit 2 ;;
esac
