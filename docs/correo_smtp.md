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

## Invitaciones y recuperación de contraseña
- Al crear un usuario en Configuración se pide su correo y su rol, no su contraseña: le llega una invitación con un enlace (vale 3 días) para crearla. Si el correo falla, aparece el error y el botón «Reenviar invitación» en la lista de usuarios.
- Quien olvidó su contraseña entra a «¿Olvidaste tu contraseña?» en el ingreso (`/recuperar/`). Recibe el mismo tipo de enlace. El doble factor no cambia.
- Si el puerto es 465 y el `.env` no tiene `EMAIL_USE_SSL=1`, la conexión se queda esperando; el sistema corta a los 20 segundos (`EMAIL_TIMEOUT`) y `probar_correo` avisa de la causa.

## Correos que envía el sistema
Todos son HTML con el logo de DH Store, una etiqueta de color que dice qué es y una línea que explica por qué se recibe, más una versión de texto plano:
| Etiqueta | Cuándo llega | A quién |
|---|---|---|
| INVITACIÓN (verde) | Al crear un usuario o «Reenviar invitación» | La persona invitada |
| RECUPERAR CONTRASEÑA (azul) | Desde «¿Olvidaste tu contraseña?» | Quien lo pide |
| ALERTA DE VENCIMIENTO (rojo) | Diario, cuando una obligación vence en 15, 7, 3 o 1 día, o ya venció | `ALERTAS_DESTINATARIOS` (o dueño y contador) |
| RESUMEN SEMANAL (azul oscuro) | Cada lunes a las 7:00 (hora de Bogotá) | `RESUMEN_SEMANAL_DESTINATARIOS` (si está vacío, los de las alertas) |
| PRUEBA DE CORREO (gris) | Al correr `probar_correo` | El correo indicado |

Variables del `.env` para el resumen y los enlaces:
```
RESUMEN_SEMANAL_DESTINATARIOS=ventas2@dhtransstorage.com.co,gerencia@dhtransstorage.com.co
SITE_URL=https://contabilidad.dhstore.com.co
```
El resumen incluye todo lo pendiente del año en curso: vencidas, próximos 30 días y lo que viene después, con el conteo de obligaciones cumplidas. Para enviarlo ahora, sin esperar al lunes: `docker compose exec web python manage.py enviar_resumen_semanal` (o `--a correo@ejemplo.com` para probar con otro destino).
