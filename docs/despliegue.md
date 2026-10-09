# Despliegue en el VPS de Hostinger (paso a paso)

Todo corre con Docker Compose en un solo VPS: Django (gunicorn), PostgreSQL, Redis, Celery (worker y beat) y Caddy (HTTPS automático).

> Antes de comprar confirma que el plan de VPS incluya **acceso root/SSH** y copias de seguridad. No verifiqué precios ni planes actuales. Tamaño inicial sugerido (a validar): 2 vCPU y 4 GB de RAM, Ubuntu LTS.

## Lo que haces tú, una sola vez

1. **Contratar el VPS** con Ubuntu LTS. Anota la IP pública.
2. **Crear una llave SSH** en tu computador (`ssh-keygen -t ed25519`) y pegar la llave *pública* al crear el VPS (o dársela al script del paso 6).
3. **Dominio o subdominio** (p. ej. `control.tudominio.com`): crea un registro DNS tipo **A** que apunte a la IP del VPS. Espera a que propague.
4. **Repositorio privado en GitHub** (ya existe: `danielhenao1/dh-control-contable`) y una **llave de despliegue de solo lectura**: en tu computador `ssh-keygen -t ed25519 -f deploy_key -N ""`; en GitHub → Settings → Deploy keys → agrega `deploy_key.pub` (sin permiso de escritura). Copia `deploy_key` (la privada) al VPS en `~/.ssh/deploy_key`.
5. **Almacenamiento externo compatible con S3** (Backblaze B2, Wasabi, DigitalOcean Spaces, AWS S3...) para las copias cifradas: crea un bucket privado y una llave de acceso solo para ese bucket. Guarda la URL del endpoint, el nombre del bucket y las dos llaves.

## En el servidor

6. **Preparar el servidor** (usuario sin root, firewall 22/80/443, fail2ban, Docker, actualizaciones automáticas y copia diaria a las 3:15 a. m.). El repositorio es privado, así que el script se copia desde tu computador (no se clona como root):
   ```bash
   # En tu computador, desde la carpeta del repositorio:
   scp deploy/bootstrap.sh root@IP_DEL_VPS:/root/
   ssh root@IP_DEL_VPS
   bash /root/bootstrap.sh control "$(cat /ruta/a/tu_llave_publica.pub)"   # o pega la llave entre comillas
   ```
   A partir de aquí **entra como `control`** (`ssh control@IP`), no como root. Verifica en una segunda terminal que el ingreso como `control` funciona *antes* de cerrar la sesión de root.
7. **Clonar el repositorio** en `/opt/control` con la llave de despliegue:
   ```bash
   cd /opt/control
   GIT_SSH_COMMAND="ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes" git clone git@github.com:danielhenao1/dh-control-contable.git .
   ```
8. **Crear el `.env`** (nunca se sube al repositorio): `cp .env.example .env` y completa:
   - `DJANGO_SECRET_KEY`: `python3 -c "import secrets; print(secrets.token_urlsafe(60))"`
   - `DJANGO_ALLOWED_HOSTS` y `DOMINIO`: tu dominio; `DJANGO_CSRF_TRUSTED_ORIGINS=https://tu-dominio`
   - `POSTGRES_PASSWORD` (y la misma clave dentro de `DATABASE_URL`)
   - `REDIS_URL=redis://redis:6379/0`
   - Correo SMTP (`EMAIL_*`) y `ALERTAS_DESTINATARIOS` para las alertas de vencimiento.
   - `BACKUP_PASSPHRASE` (**guárdala también en un gestor de contraseñas: sin ella no se restauran las copias**), `BACKUP_S3_*`, `AWS_*`.
   - `ANTHROPIC_API_KEY` solo si quieres que el asistente redacte explicaciones (opcional).
   `chmod 600 .env`.
9. **Levantar**:
   ```bash
   docker compose up -d --build
   docker compose exec web python manage.py cargar_datos_iniciales
   docker compose exec web python manage.py createsuperuser
   ```
   Caddy obtiene el certificado HTTPS solo cuando el DNS ya apunta al VPS. Abre `https://tu-dominio`. En `/admin/` asigna el rol **Dueño** a tu usuario, vuelve a entrar y configura el doble factor (escaneas el QR y guardas los 8 códigos de recuperación).
10. **Crear los usuarios** (Configuración → Nuevo usuario): dueño, contador/revisor en solo lectura, asistente de carga y el contratista con acceso limitado.

## Actualizar (cada despliegue)

```bash
cd /opt/control
GIT_SSH_COMMAND="ssh -i ~/.ssh/deploy_key -o IdentitiesOnly=yes" git pull
docker compose up -d --build
docker compose exec web python manage.py migrate   # ya corre al arrancar; sirve para ver el resultado
```

### Lista de verificación por despliegue
- [ ] `git log -1` muestra el commit esperado y las pruebas de CI pasaron.
- [ ] `docker compose ps`: todos los servicios arriba (`web`, `worker`, `beat`, `db`, `redis`, `caddy`).
- [ ] `https://tu-dominio/salud/` responde `ok` y el candado HTTPS es válido.
- [ ] Ingreso con doble factor funciona; un usuario `consulta` no ve Configuración.
- [ ] Tablero muestra el aviso de parámetros por verificar hasta que el contador los confirme.
- [ ] Hay una copia reciente en `/var/backups/control` y en el bucket externo.

## Copias de seguridad (regla 3-2-1)

- **Tres copias:** la base en uso, la copia diaria cifrada en el servidor (`/var/backups/control`, 14 días) y la copia en el bucket externo, además de las copias del propio proveedor del VPS.
- **Manual:** `./deploy/backup.sh`. **Restaurar:** `./deploy/restore.sh /var/backups/control/control-AAAAMMDD-HHMMSS.tar.gz.gpg`.
- **Cada mes** prueba una restauración completa en un entorno limpio (otro VPS pequeño o local con `docker-compose.dev.yml`) y confirma que puedes ingresar y ver una carga reciente. Sin esa prueba, no hay copia.

## Seguridad que ya queda aplicada

Firewall con solo 22 (con llave), 80 y 443 · SSH sin contraseña ni root · fail2ban · actualizaciones automáticas · base de datos sin puerto publicado · HTTPS obligatorio con HSTS · doble factor y bloqueo de intentos · sesión que cierra a los 30 min de inactividad · secretos solo en `.env`.

Las credenciales no se comparten por chat ni por correo; la llave de despliegue es de solo lectura y revocable desde GitHub.
