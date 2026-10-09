# Estado del proyecto

Archivo de continuidad entre sesiones. Léelo junto con `CLAUDE.md`, `docs/PROGRESO.md` (checklist por fases) y `docs/decisiones.md`. **Actualízalo al cerrar cada sesión de trabajo.** Última actualización: 9-oct-2026 (decisiones de despliegue).

## Despliegue (9-oct-2026): el sistema ya corre en el VPS
- **En vivo:** `https://contabilidad.dhstore.com.co` (VPS Hostinger KVM 4, Ubuntu 26.04 LTS, IP 31.97.136.172). Docker Compose con `db`, `redis`, `web`, `worker`, `beat` y `caddy`; HTTPS con Let's Encrypt; doble factor funcionando; usuario `DanielH` con rol dueño. Servidor endurecido con `deploy/bootstrap.sh` (usuario `control` con sudo, SSH solo por llave, root sin acceso SSH, ufw 22/80/443, fail2ban).
- **Código en el servidor:** `/opt/control` (clonado con llave de despliegue **de solo lectura**). Para actualizar: `cd /opt/control && git pull && docker compose up -d --build web worker beat && docker compose exec web python manage.py cargar_datos_iniciales`.
- **Datos:** solo los iniciales. Todavía **no** se han cargado datos contables reales.
- **Pendiente antes de datos reales:** copia de seguridad fuera del servidor (`docs/respaldo_en_mi_pc.md`) y prueba de restauración (puerta P0).
- **Correo (SMTP):** **no configurado**. Hoy el sistema solo envía por correo las alertas de vencimiento y, sin `EMAIL_HOST`, salen por la consola del servidor. No envía invitaciones a usuarios nuevos ni correos de recuperación de contraseña: el dueño crea los usuarios en Configuración y les entrega la contraseña por un canal seguro; cada uno configura su doble factor al primer ingreso. Para activarlo: `EMAIL_*` en el `.env` (puerto 587 con `EMAIL_USE_TLS=1`, o 465 con `EMAIL_USE_SSL=1` y `EMAIL_USE_TLS=0`), `DEFAULT_FROM_EMAIL` y `ALERTAS_DESTINATARIOS`. El dominio ya tiene correo de Hostinger (MX/SPF/DKIM); falta crear el buzón y confirmar los datos del servidor SMTP en su panel.
- **Usuarios y roles:** ver `docs/usuarios_y_roles.md` (incluye cómo poner a una persona a cargar los archivos mensuales con el rol *Asistente de carga*).
- **ICA y ReteICA de Bogotá (9-oct-2026):** cargadas con fuente las fechas de ICA bimestral 2026 (10-abr, 12-jun, 21-ago, 9-oct, 11-dic, 12-feb-2027), ICA bimestre 6 de 2025 (13-feb-2026) y ReteICA bimestral (16-ene, 20-mar, 22-may, 17-jul, 18-sep, 20-nov-2026 y 15-ene-2027). Resolución SDH-000195 de 2025 y comunicados de la SDH. **ReteICA de sep-oct y nov-dic 2026 y el de jul-ago 2026 vienen de una sola fuente (prensa): verificar con la resolución.** El ICA anual solo aplica al régimen anual (la empresa declara bimestral): confirmar. Todo lo vencido hasta el 9-oct está presentado y pagado.
- **Exógena (9-oct-2026):** cargadas con fuente la **DIAN AG 2025** (NIT terminado en 49 → 28-may-2026; hubo plazos extraordinarios al 31-ago-2026 solo para ciertos formatos) y la **distrital de Bogotá AG 2025** (Resolución DDI-024115 del 27-jul-2026; dígito 9 → **26-oct-2026**, plataforma PIDO). **La distrital vence en pocos días: confirmar con el contador/Ideako que se presenta.** AG 2026 (se reporta en 2027): sin fecha publicada. Estado de la exógena DIAN 2025: por confirmar si se presentó.
- **Marca:** logo DH Store y favicon en `static/img/` (generados a partir del logo entregado por el dueño); el diseño se seguirá mejorando.
- **Calendario:** `CALENDARIO_DESDE = 2026-01-01` (no se crea nada anterior). Se generan desde 2025 los períodos que vencen en 2026 (retención dic-2025, IVA 3.er cuatrimestre 2025, renta AG 2025), todos marcados presentados y pagados. Se mantiene solo (tarea diaria `generar_calendario_automatico`: año en curso y el siguiente). Las fechas de **ICA Bogotá** son fijas y salen de la resolución de cada año: hay que cargar la regla del año nuevo (si no, no se inventa).

## Dónde estamos
- Fases F0–F5 del plan construidas y fusionadas en `main` (PR #1). Sistema Django completo con datos sintéticos; **nunca se ha ejecutado con datos reales ni en el VPS**.
- Rama de trabajo de la sesión: `claude/document-review-sd30p4` (reiniciada desde `main` tras el merge).
- **Decisiones del dueño (9-oct-2026):** proveedor VPS = Hostinger (plan por confirmar); subdominio = `contabilidad.dhstore.com.co`; un solo VPS (KVM 4, Ubuntu 26.04 LTS, 200 GB; IP 31.97.136.172, host srv885245.hstgr.cloud) ya contratado; asistente de IA **apagado** hasta terminar las pruebas; **sin S3 ni SMTP por ahora**. Copia de seguridad fuera del servidor: **pendiente**, se empieza en producción (`docs/respaldo_en_mi_pc.md`); **debe estar activa antes del primer dato contable real**.
- **Despliegue: pendiente de aprobación.** Plan en `docs/plan_despliegue_hostinger.md`; guía paso a paso en `docs/despliegue.md`. No se ha tocado ningún servidor ni se han pedido credenciales.

## Datos confirmados con el certificado de la Cámara de Comercio (expedido 1-sep-2026)
- Matrícula mercantil de la sociedad renovada el **29-abr-2026** (último año renovado: 2026); los establecimientos DH LAPTOP STORAGE y DH BOOKS también figuran renovados 2026. El plazo legal general es el 31-mar: la renovación fue posterior; si hubo sanción o un plazo distinto, confirmar con la Cámara.
- **Grupo NIIF III** y tamaño **microempresa** (ingresos por actividad ordinaria reportados en RUES: $1.626.389.817, muy por debajo del tope de IVA bimestral ≈ $4.581 millones): consistente con IVA cuatrimestral. El Grupo 3 usa el marco simplificado para microempresas del Decreto 2420 de 2015: revisar con el contador qué estados e indicadores aplican.
- CIIU: principal 4651, secundaria 4923, otras 5320 y **5210**. El RUT listaba 5320 y 9511: **discrepancia por aclarar** (afecta tarifa de ICA).
- Inscrito en el RIT (Bogotá) desde el 3-ene-2017.
- Los datos personales del certificado (documentos de identidad) no se guardan en el repositorio.

## Estado del calendario (decisión del dueño, 9-oct-2026)
Todos los impuestos con vencimiento **hasta el 9-oct-2026** (retefuente, IVA, ICA) se marcan "presentada y pagada", sin evidencia cargada. Solo queda pendiente la **retención de septiembre, vence el 22-oct-2026** (Ideako). `CONTROL_DESDE = 2026-10-01`: lo anterior no genera alertas. Fechas laborales (cesantías, prima): por definir si aplican (¿hay empleados con contrato laboral?).

## Historial del CI (qué falló y por qué)
| Corrida | Commit | Resultado | Causa | Solución |
|---|---|---|---|---|
| 1 | `899989f` (rama) | ❌ ruff | Imports sin ordenar en archivos nuevos | Corregido con `ruff --fix` en `be7249d` |
| 2 y 3 | `be7249d` (rama y PR) | ✅ | — | — |
| 4 | `bb37121` (`main`, tras el merge) | ❌ pytest contra PostgreSQL | Prueba inestable `test_flujo_de_carga_y_vigencia`: generaba el `.xlsx` dos veces y el archivo lleva marca de tiempo, así que a veces los bytes (y la huella) diferían y no se detectaba el duplicado. Error de la prueba, no del producto | Se genera el contenido una sola vez (commit de esta rama) |

Nota: el merge se hizo viendo verdes las corridas del PR; la corrida sobre `main` falló después por la prueba inestable descrita. Lección: esperar también el CI de `main` antes de dar algo por cerrado.

## Pendiente (en orden)
1. Aprobación del plan de despliegue; Elegir proveedor S3 y SMTP (S3 es obligatorio antes de datos reales). Ver `plan_despliegue_hostinger.md` §7.
2. Desplegar en el VPS y pasar P0 (HTTPS, 2FA, restauración de copia).
3. P1–P4 con datos reales: ver `docs/pendientes.md` (formatos de World Office/DIAN, parámetros del contador, tarifas, topes, prefijos de cuentas).
4. Tras las pruebas de aceptación con datos sintéticos: decidir si se activa el asistente de IA (`plan_despliegue_hostinger.md` §8).
5. Mejoras fuera del MVP: vendorizar Chart.js, importación asíncrona, API.

## Cómo retomar una sesión
```bash
git fetch origin && git checkout main && git pull
python -m venv .venv && source .venv/bin/activate && pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
ruff check . && pytest            # debe quedar todo en verde
```
Comandos útiles: `python manage.py cargar_datos_iniciales`, `ejecutar_controles --anio 2026 --mes 9`, `verificar_calendario`, `generar_festivos 2028 2030`.

## Reglas que no se rompen
Ver `CLAUDE.md`. En especial: no inventar tarifas/normas, parámetros solo en tablas con vigencia, la IA nunca calcula, archivos nunca se sobrescriben, nada de datos reales ni secretos en el repositorio.

## Supuestos abiertos (validar con archivos reales)
- Saldo final del balance positivo en la naturaleza de la cuenta; Débitos/Créditos del mes y resultados acumulados (`docs/decisiones.md` #5).
- Prefijos de cuentas (`PUC_*`) con el PUC comercial estándar, por confirmar.
- Tarifa de renta 35 %, tasa mínima 15 % y UVT 2025: cargadas "por verificar".
