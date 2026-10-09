# Escalabilidad, migración de servidor y varias empresas

## Escalabilidad
- **Hoy:** un VPS con Docker Compose (web con gunicorn de 3 procesos, worker y beat de Celery, Redis, PostgreSQL, Caddy). Es suficiente para una empresa y pocos usuarios.
- **Crecer sin rediseñar:** subir el plan del VPS, más procesos de gunicorn y de Celery, y separar PostgreSQL en un servicio administrado. La aplicación no guarda estado en el proceso (las sesiones y los datos van a la base; Redis atiende a Celery y la caché; los archivos cargados van al volumen `media`, que habría que compartir si hubiera varios servidores web).
- **Límites conocidos:** la importación de archivos grandes corre dentro de la petición (mejora futura: hacerla asíncrona con Celery); Chart.js se carga desde un CDN (mejora futura: servirlo local).

## Migrar de servidor
Es posible y está previsto:
1. En el servidor actual: `./deploy/backup.sh` (base de datos y archivos, cifrado con la frase `BACKUP_PASSPHRASE`).
2. En el nuevo: `deploy/bootstrap.sh`, clonar el repositorio y copiar el `.env` por un canal seguro (mismas `DJANGO_SECRET_KEY` y `BACKUP_PASSPHRASE`).
3. `./deploy/restore.sh <copia>` y `docker compose up -d --build`.
4. Cambiar el DNS de `contabilidad.dhstore.com.co` a la IP nueva; Caddy emite el certificado solo.
Antes del cambio definitivo se recomienda ensayar la restauración en el servidor nuevo. Requisito: la copia de seguridad fuera del servidor (pendiente) debe estar activa.

## Varias empresas en el mismo dominio
**Hoy no está soportado.** El sistema se diseñó para una sola empresa: `Empresa.actual()` devuelve la primera y las demás tablas (cargas, terceros, facturas, obligaciones, hallazgos, parámetros, auditoría) no tienen vínculo con una empresa.

Para soportarlo hay que hacer un cambio grande, que conviene planear aparte:
- Agregar `empresa` a cada modelo de datos y filtrar todas las consultas por la empresa activa.
- Selector de empresa en el encabezado y permisos por usuario y empresa (un usuario puede ver unas empresas y otras no).
- Parámetros, calendario (por NIT), mapeos de importación y auditoría por empresa; el calendario depende del último dígito del NIT.
- Migración de datos: la empresa actual pasa a ser la empresa 1.
- Pruebas de aislamiento: ninguna consulta debe mezclar datos entre empresas.
Alternativa más simple: una instalación separada por empresa (otro subdominio y otro contenedor), con aislamiento total, a costa de mantener varias instalaciones.

## Decisión del dueño (9-oct-2026)
Por ahora cada empresa va en una **instalación separada** (otro subdominio y otro contenedor). Más adelante se decidirá entre clonar esta instalación por empresa o pasar todo a un solo sistema con varias empresas.
