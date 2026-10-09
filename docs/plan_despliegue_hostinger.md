# Diagnóstico técnico y plan de despliegue en Hostinger

**Estado: propuesta para aprobación. No se ha ejecutado nada ni se ha tocado ningún servidor.** La guía operativa con todos los comandos es [`despliegue.md`](despliegue.md); este documento la justifica y agrega pruebas, fallos y criterios de avance.

## 1. Diagnóstico

### Tecnología
| Capa | Qué usa |
|---|---|
| Lenguaje y framework | Python 3.12, Django 5.2 (monolito, plantillas + CSS propio + Chart.js por CDN) |
| Base de datos | PostgreSQL 16 (en desarrollo y pruebas, SQLite) |
| Tareas en segundo plano | Celery (worker + beat) con Redis 7: alertas de vencimiento, recálculo de controles |
| Servidor de aplicación | gunicorn detrás de Caddy 2 (HTTPS automático con Let's Encrypt) |
| Archivos | Cargas en volumen Docker `media` (con huella SHA-256, nunca se sobrescriben) |
| Librerías del sistema | Pango/HarfBuzz para el PDF (ya incluidas en `docker/Dockerfile`) |
| Orquestación | Docker Compose: `db`, `redis`, `web`, `worker`, `beat`, `caddy` |

Dependencias exactas: `requirements.txt`. CI en GitHub Actions (ruff, migraciones, pytest con SQLite y con PostgreSQL).

### Variables de entorno (`.env`, nunca en el repositorio; plantilla en `.env.example`)
| Variable | Obligatoria | Para qué |
|---|---|---|
| `DJANGO_SECRET_KEY` | Sí | Firma de sesiones; sin ella la app no arranca en producción |
| `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DOMINIO` | Sí | Dominio de acceso |
| `POSTGRES_PASSWORD`, `DATABASE_URL` | Sí | Base de datos (misma clave en ambas) |
| `REDIS_URL` | Sí | Broker de Celery y caché |
| `EMAIL_*`, `DEFAULT_FROM_EMAIL`, `ALERTAS_DESTINATARIOS` | Recomendada | Alertas de vencimiento por correo |
| `BACKUP_PASSPHRASE`, `BACKUP_S3_BUCKET`, `BACKUP_S3_ENDPOINT`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Sí para cumplir 3-2-1 | Copias cifradas fuera del servidor |
| `ANTHROPIC_API_KEY`, `ASISTENTE_MODELO` | Opcional | Asistente que redacta explicaciones (recibe datos minimizados) |
| `OTP_OBLIGATORIO`, `SESSION_COOKIE_AGE`, `LOGIN_INTENTOS_MAX` | No | Ajustes de seguridad (valores seguros por defecto) |

### ¿VPS o el hosting que ya tienes?
**Requiere VPS.** El sistema necesita PostgreSQL, Redis, procesos permanentes (Celery), Docker y acceso root. La documentación oficial de Hostinger indica que Django no puede correr en sus planes de hosting web/cloud compartido porque no dan acceso root, y que sí corre en sus planes VPS ([Is Django supported at Hostinger?](https://www.hostinger.com/support/?p=1382)). Lo que **no pude confirmar** es si Docker tiene restricciones en el VPS de Hostinger (las fuentes consultadas no lo cubren): se valida en la etapa 0 con `docker run hello-world` antes de seguir. Tampoco verifiqué precios ni planes actuales.

> Necesito de ti: qué plan de Hostinger tienes contratado hoy (hosting web, Cloud o VPS). Si es hosting compartido, hay que contratar un VPS aparte; el hosting actual puede seguir sirviendo el correo o el dominio.

Tamaño inicial sugerido (a validar con uso real): 2 vCPU, 4 GB de RAM, 40 GB de disco, Ubuntu 22.04/24.04 LTS.

## 2. Plan por etapas (cada una con verificación y marcha atrás)

Cada etapa se ejecuta solo después de tu aprobación explícita. Ninguna requiere que me entregues contraseñas: las claves las creas tú en el servidor y nunca pasan por el chat.

| # | Etapa | Comandos clave (detalle en `despliegue.md`) | Verificación | Si falla |
|---|---|---|---|---|
| 0 | Contratar VPS, DNS tipo A, llaves SSH, bucket S3, llave de despliegue de solo lectura | Pasos 1–5 de `despliegue.md` | `ssh` por llave funciona; `dig +short tu-dominio` devuelve la IP; `docker run hello-world` corre tras el paso 6 | No avanzar; se resuelve con soporte del proveedor |
| 1 | Endurecer el servidor | `bash bootstrap.sh control "<llave pública>"` | `sudo ufw status` (22/80/443); `sudo fail2ban-client status sshd`; ingreso como `control` y root deshabilitado | Entrar por la consola web de Hostinger y revisar `/etc/ssh/sshd_config` (por eso se prueba el segundo acceso antes de cerrar root) |
| 2 | Código y `.env` | `git clone` con la llave de despliegue en `/opt/control`; `cp .env.example .env`; `chmod 600 .env` | `ls -l .env` = `-rw-------`; `git log -1` = commit esperado | Borrar y recrear el `.env` |
| 3 | Levantar servicios | `docker compose up -d --build` | `docker compose ps` todo `running`; `docker compose logs web --tail 50` sin errores | `docker compose logs <servicio>`; corregir `.env`; `docker compose up -d` de nuevo |
| 4 | Migraciones y datos iniciales | Las migraciones corren al arrancar `web`. Luego `docker compose exec web python manage.py cargar_datos_iniciales` y `createsuperuser` | `docker compose exec web python manage.py showmigrations \| grep '\[ \]'` no devuelve nada | Ver §5 (migración fallida) |
| 5 | HTTPS | Automático con Caddy cuando el DNS ya apunta al VPS | `curl -I https://contabilidad.dhstore.com.co/salud/` → 200 y `strict-transport-security`; candado válido | Si no emite certificado: DNS aún sin propagar, puerto 80 cerrado o dominio mal escrito en `.env` (`docker compose logs caddy`) |
| 6 | Doble factor y usuarios | Ingreso, QR, guardar 8 códigos de recuperación; crear usuarios por rol | Un usuario `consulta` no ve Configuración (403) | Código de recuperación; en último caso `docker compose exec web python manage.py shell` para reasignar dispositivo (con tu autorización) |
| 7 | Copias | `./deploy/backup.sh` manual una vez | Archivo `.gpg` en `/var/backups/control` **y** en el bucket | Revisar `BACKUP_*`, `gpg`, `aws` |
| 8 | Restauración (puerta P0) | `./deploy/restore.sh <archivo>` en un entorno limpio | Ingresar y ver la carga de prueba | Sin restauración exitosa no se pasa a datos reales |
| 9 | Pruebas con datos sintéticos | §4 | Lista de comprobación | — |
| 10 | Datos reales | Solo tras P0 y con aprobación | Ver `pendientes.md` | — |

## 3. Seguridad de credenciales
- Todas las claves viven solo en `/opt/control/.env` (permisos 600) y en tu gestor de contraseñas. **Nunca por chat, correo ni en el repositorio.** Yo no necesito ninguna para preparar o revisar este plan.
- Acceso al servidor: SSH solo con llave, sin contraseña ni root. Llave de despliegue de GitHub de **solo lectura** y revocable.
- `BACKUP_PASSPHRASE`: guárdala fuera del servidor; sin ella las copias no se restauran.
- Rotación: si una clave se expone, cambiar `DJANGO_SECRET_KEY` (cierra todas las sesiones), la clave de PostgreSQL (en `.env` y con `ALTER USER`), revocar llaves de S3 y de GitHub.
- La base de datos no publica puertos; el firewall solo abre 22, 80 y 443.

## 4. Cómo probar sin datos contables reales
1. Desplegar con la base vacía y correr `cargar_datos_iniciales` (solo trae la empresa, parámetros marcados "por verificar", reglas de calendario y el contratista; **no trae movimientos contables**).
2. Usar únicamente los CSV sintéticos: el del README (balance de 3 cuentas) y archivos inventados de auxiliares y facturas con NIT ficticios (p. ej. 900123456) y valores redondos. No subir ningún exporte real de World Office ni de la DIAN.
3. Recorrido de aceptación: ingreso con 2FA → cargar balance → ver vista previa → confirmar → ver hallazgos (el balance descuadrado del ejemplo debe disparar INT001) → duplicar la carga (debe avisar "ya fue cargado") → cerrar el periodo y comprobar que bloquea nuevas cargas → generar informe PDF/Excel → ver calendario (22-oct-2026 retención) → usuario `consulta` sin acceso a Configuración.
4. Probar una caída: `docker compose restart web` y `docker compose down && up -d` sin perder datos; ejecutar backup + restore en un entorno limpio.
5. Antes de usar datos reales: borrar los datos de prueba (volver a un entorno limpio con `docker compose down -v` **solo en el entorno de pruebas**) o usar un periodo de prueba claramente separado y cerrado.

## 5. Recuperación ante fallos
| Situación | Qué hacer |
|---|---|
| Despliegue nuevo falla | `git log` → volver al commit anterior (`git checkout <sha>`), `docker compose up -d --build`. Las migraciones aplicadas no se revierten solas: ver siguiente fila |
| Migración falla a mitad | Antes de cada despliegue con migraciones: `./deploy/backup.sh`. Si falla, restaurar esa copia con `restore.sh` y volver al commit anterior |
| Contenedor cae en bucle | `docker compose logs --tail 100 <servicio>`; todos tienen `restart: unless-stopped` |
| Disco lleno | `docker system prune` (sin `-a --volumes`), `df -h`, rotar copias antiguas (ya se conservan 14 días) |
| Servidor perdido | Nuevo VPS → etapas 1–3 → `restore.sh` con la última copia del bucket externo y la misma `BACKUP_PASSPHRASE` |
| Certificado no renueva | `docker compose logs caddy`; verificar DNS y puerto 80 |
| Pérdida del celular del 2FA | Código de recuperación; si no, reasignación por el administrador con autorización |

## 6. Hallazgos de revisión previos al despliegue (ya corregidos)
- El paso 6 de la guía clonaba el repositorio **privado** como root con HTTPS sin credenciales: ahora el script se copia con `scp`.
- `backup.sh`/`restore.sh` usaban `gpg --passphrase` sin `--pinentry-mode loopback`, que falla en `gpg` ≥ 2.1 sin terminal: corregido.
- El CI falló dos veces antes de quedar en verde (ver `ESTADO_PROYECTO.md`).

## 7. Decisiones tomadas y pendientes

| Tema | Estado |
|---|---|
| Proveedor de VPS | **Hostinger, un solo VPS ya contratado**: KVM 4, Ubuntu 26.04 LTS, 200 GB de disco, 16 TB de ancho de banda, IPv4 31.97.136.172 (srv885245.hstgr.cloud). Es VPS con acceso root: cumple el requisito. Pendiente validar `docker run hello-world` en este sistema (Ubuntu 26.04 es reciente) |
| Subdominio | **`contabilidad.dhstore.com.co`** → registro DNS tipo A hacia la IP del VPS; en `.env`: `DOMINIO=contabilidad.dhstore.com.co`, `DJANGO_ALLOWED_HOSTS=contabilidad.dhstore.com.co`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://contabilidad.dhstore.com.co` |
| Asistente de IA | **Apagado por ahora** (`ANTHROPIC_API_KEY` vacío; el botón usa la plantilla local, sin enviar nada fuera). Se activa **después de probar todo el sistema**, añadiendo la clave solo en el `.env` del servidor y reiniciando `web` (ver §8) |
| Copia fuera del servidor | **Sin S3.** El dueño prefiere traer las copias a su computador (`docs/respaldo_en_mi_pc.md`) o a otro VPS más adelante. **Pendiente: se empieza en producción, y debe estar activa antes de cargar el primer dato contable real** (puerta P0) |
| Correo SMTP para alertas | **Pendiente**. Sin SMTP las alertas salen por consola del servidor; siguen visibles en tablero y calendario. Se necesita antes de depender de los avisos por correo |
| Plan de Hostinger actual | **Confirmado: VPS** (ver arriba). Un solo VPS; copias en bucket S3, sin segundo VPS |

Orden sugerido con lo pendiente: (a) confirmar/contratar el VPS; (b) etapas 0–8 con datos sintéticos, sin S3 ni SMTP; (c) elegir proveedor S3 y SMTP; (d) pasar P0 con restauración desde el bucket externo; (e) datos reales.

## 8. Activar el asistente de IA (después de las pruebas)

Condiciones: pruebas de aceptación de §4 completas y revisadas; decisión explícita del dueño.
1. Crear la clave de API en la consola de Anthropic (con límite de gasto mensual) y guardarla en el gestor de contraseñas. **No compartirla por chat.**
2. En el servidor: editar `/opt/control/.env` y poner `ANTHROPIC_API_KEY=...` (el modelo se controla con `ASISTENTE_MODELO`).
3. `docker compose up -d web worker` para recargar.
4. Verificar: abrir un hallazgo de prueba → “Redactar explicación con el asistente” → el pie del texto debe indicar el modelo (y no “local”), y debe aparecer una fila `ia` en Auditoría.
5. Qué sale del servidor: solo el hallazgo ya calculado con NIT, correos y números largos reemplazados por marcas. Nunca balances, auxiliares ni facturas completas. Retirar la clave del `.env` lo apaga de inmediato.
