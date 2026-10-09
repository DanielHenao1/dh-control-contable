#!/usr/bin/env bash
# Prepara un VPS Ubuntu LTS limpio: usuario sin root, firewall, fail2ban, Docker y copias diarias.
# Ejecutar UNA vez como root:  sudo bash deploy/bootstrap.sh <usuario_nuevo> "<llave_publica_ssh>"
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Ejecuta como root (sudo)."; exit 1; }
USUARIO=${1:?Indica el nombre del usuario nuevo (p. ej. control)}
LLAVE=${2:?Indica la llave pública SSH entre comillas}

export DEBIAN_FRONTEND=noninteractive
apt-get update && apt-get -y upgrade
apt-get install -y ufw fail2ban unattended-upgrades gnupg ca-certificates curl git unzip

# AWS CLI (para subir las copias al bucket S3): paquete de Ubuntu si existe; si no, instalador oficial de AWS
if ! command -v aws &>/dev/null; then
  apt-get install -y awscli || {
    curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o /tmp/awscliv2.zip
    unzip -q -o /tmp/awscliv2.zip -d /tmp && /tmp/aws/install && rm -rf /tmp/aws /tmp/awscliv2.zip
  }
fi

# Usuario sin root con llave SSH
id "$USUARIO" &>/dev/null || adduser --disabled-password --gecos "" "$USUARIO"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "/home/$USUARIO/.ssh"
echo "$LLAVE" > "/home/$USUARIO/.ssh/authorized_keys"
chown "$USUARIO:$USUARIO" "/home/$USUARIO/.ssh/authorized_keys"; chmod 600 "/home/$USUARIO/.ssh/authorized_keys"

# El usuario puede administrar el servidor con sudo (sin contraseña: solo entra con llave, y root queda sin acceso SSH)
usermod -aG sudo "$USUARIO"
echo "$USUARIO ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-$USUARIO"
chmod 440 "/etc/sudoers.d/90-$USUARIO"
visudo -cf "/etc/sudoers.d/90-$USUARIO"

# SSH solo con llave, sin root. Se usa un archivo que se lee primero (00-) para que ningún otro archivo de
# /etc/ssh/sshd_config.d/ (p. ej. el de la imagen del proveedor) lo anule.
cat > /etc/ssh/sshd_config.d/00-control.conf <<'SSHD'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
SSHD
sshd -t
systemctl reload ssh || systemctl reload sshd
# Comprueba que la configuración efectiva quedó como se espera
sshd -T | grep -E '^(passwordauthentication|permitrootlogin) '

# Firewall: solo 22 (llave), 80 y 443
ufw default deny incoming; ufw default allow outgoing
ufw allow 22/tcp; ufw allow 80/tcp; ufw allow 443/tcp
ufw --force enable

# fail2ban para SSH
cat > /etc/fail2ban/jail.d/control.local <<'JAIL'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
JAIL
systemctl enable --now fail2ban && systemctl restart fail2ban

# Actualizaciones de seguridad automáticas
dpkg-reconfigure -f noninteractive unattended-upgrades || true

# Docker
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
usermod -aG docker "$USUARIO"

# Directorio de la aplicación y copias diarias (3:15 a. m.)
install -d -o "$USUARIO" -g "$USUARIO" /opt/control
install -d -m 700 -o root -g root /var/backups/control
cat > /etc/cron.d/control-backup <<CRON
15 3 * * * $USUARIO cd /opt/control && ./deploy/backup.sh >> /var/log/control-backup.log 2>&1
CRON
touch /var/log/control-backup.log && chown "$USUARIO" /var/log/control-backup.log
chown "$USUARIO" /var/backups/control && chmod 700 /var/backups/control

echo "Listo. Entra con:  ssh $USUARIO@<ip>   y sigue docs/despliegue.md (paso: clonar el repositorio en /opt/control)."
