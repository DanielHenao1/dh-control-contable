# Configurar el correo (SMTP)

El sistema usa el correo para las alertas de vencimiento. No envía invitaciones ni recuperación de contraseña (ver `docs/pendientes.md`).

## 1. Crear el buzón
En el panel de Hostinger, sección Correo del dominio `dhstore.com.co`, crea un buzón para el sistema, por ejemplo `control@dhstore.com.co`. El dominio ya tiene MX, SPF y DKIM.

## 2. Datos del servidor
Confírmalos en el panel de Hostinger (Correo, Configuración): servidor saliente, puerto y tipo de cifrado. Valores habituales de Hostinger, por confirmar: servidor `smtp.hostinger.com`, puerto 465 con SSL o 587 con STARTTLS. Usuario = la dirección completa del buzón.

## 3. Editar el `.env` en el servidor
Sin mostrar el archivo en capturas ni pegar la contraseña en el chat:

```bash
cd /opt/control && nano .env
```

```
EMAIL_HOST=smtp.hostinger.com
EMAIL_PORT=465
EMAIL_USE_SSL=1
EMAIL_USE_TLS=0
EMAIL_HOST_USER=control@dhstore.com.co
EMAIL_HOST_PASSWORD=<contraseña del buzón>
DEFAULT_FROM_EMAIL=DH Control Contable <control@dhstore.com.co>
ALERTAS_DESTINATARIOS=correo1@ejemplo.com,correo2@ejemplo.com
```

Para el puerto 587 usa `EMAIL_PORT=587`, `EMAIL_USE_TLS=1` y `EMAIL_USE_SSL=0`.

## 4. Aplicar y probar
```bash
cd /opt/control && docker compose up -d web worker beat
docker compose exec web python manage.py probar_correo tu_correo@ejemplo.com
```
El comando imprime servidor, puerto y cifrado (nunca la contraseña) y confirma el envío o muestra el motivo del fallo.
