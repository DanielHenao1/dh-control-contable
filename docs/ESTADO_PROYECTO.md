# Estado del proyecto

Archivo de continuidad entre sesiones. Léelo junto con `CLAUDE.md`, `docs/PROGRESO.md` (checklist por fases) y `docs/decisiones.md`. **Actualízalo al cerrar cada sesión de trabajo.** Última actualización: 9-oct-2026 (sistema en producción, listo para empezar con datos reales).

## Despliegue (9-oct-2026): el sistema ya corre en el VPS
- **En vivo:** `https://contabilidad.dhstore.com.co` (VPS Hostinger KVM 4, Ubuntu 26.04 LTS, IP 31.97.136.172). Docker Compose con `db`, `redis`, `web`, `worker`, `beat` y `caddy`; HTTPS con Let's Encrypt; doble factor funcionando; usuario `DanielH` con rol dueño. Servidor endurecido con `deploy/bootstrap.sh` (usuario `control` con sudo, SSH solo por llave, root sin acceso SSH, ufw 22/80/443, fail2ban).
- **Código en el servidor:** `/opt/control` (clonado con llave de despliegue **de solo lectura**). Para actualizar: `cd /opt/control && git pull && docker compose up -d --build --force-recreate web worker beat && docker compose exec web python manage.py cargar_datos_iniciales` (`--force-recreate` para que tome los cambios del `.env`).
- **Datos:** solo los iniciales. Todavía **no** se han cargado datos contables reales.
- **Pendiente antes de datos reales:** copia de seguridad fuera del servidor (`docs/respaldo_en_mi_pc.md`) y prueba de restauración (puerta P0).
- **Correo (SMTP):** buzón `contacto@dhstore.com.co` (smtp.hostinger.com, puerto 465 con SSL: `EMAIL_USE_SSL=1` y `EMAIL_USE_TLS=0`). Se configura solo en el `.env` del servidor (la contraseña nunca va al repositorio) y se prueba con `python manage.py probar_correo <correo>`. Envía alertas de vencimiento, **invitaciones a usuarios nuevos** (el dueño crea el usuario con correo y rol; la persona crea su contraseña con un enlace de 3 días y luego configura su doble factor) y **recuperación de contraseña** (`/recuperar/`, limitada a 5 solicitudes por IP y hora). El doble factor no se salta con la recuperación. Pendiente del dueño: confirmar que el envío funciona en el servidor tras corregir el `.env`.
- **Usuarios y roles:** ver `docs/usuarios_y_roles.md` (incluye cómo poner a una persona a cargar los archivos mensuales con el rol *Asistente de carga*).
- **ICA y ReteICA de Bogotá (9-oct-2026):** cargadas con fuente las fechas de ICA bimestral 2026 (10-abr, 12-jun, 21-ago, 9-oct, 11-dic, 12-feb-2027), ICA bimestre 6 de 2025 (13-feb-2026) y ReteICA bimestral (16-ene, 20-mar, 22-may, 17-jul, 18-sep, 20-nov-2026 y 15-ene-2027). Resolución SDH-000195 de 2025 y comunicados de la SDH. **ReteICA de sep-oct y nov-dic 2026 y el de jul-ago 2026 vienen de una sola fuente (prensa): verificar con la resolución.** El ICA anual solo aplica al régimen anual (la empresa declara bimestral): confirmar. Todo lo vencido hasta el 9-oct está presentado y pagado.
- **Exógena (9-oct-2026):** cargadas con fuente la **DIAN AG 2025** (NIT terminado en 49 → 28-may-2026; hubo plazos extraordinarios al 31-ago-2026 solo para ciertos formatos) y la **distrital de Bogotá AG 2025** (Resolución DDI-024115 del 27-jul-2026; dígito 9 → **26-oct-2026**, plataforma PIDO). **La distrital vence en pocos días: confirmar con el contador/Ideako que se presenta.** AG 2026 (se reporta en 2027): sin fecha publicada. Estado de la exógena DIAN 2025: por confirmar si se presentó.
- **Marca:** logo DH Store y favicon en `static/img/` (generados a partir del logo entregado por el dueño); el diseño se seguirá mejorando.
- **Calendario:** `CALENDARIO_DESDE = 2026-01-01` (no se crea nada anterior). Se generan desde 2025 los períodos que vencen en 2026 (retención dic-2025, IVA 3.er cuatrimestre 2025, renta AG 2025), todos marcados presentados y pagados. Se mantiene solo (tarea diaria `generar_calendario_automatico`: año en curso y el siguiente). Las fechas de **ICA Bogotá** son fijas y salen de la resolución de cada año: hay que cargar la regla del año nuevo (si no, no se inventa).

## Dónde estamos (9-oct-2026)
- Sistema completo desplegado en `https://contabilidad.dhstore.com.co` y fusionado en `main` hasta el PR #19 (CI de `main` en verde). **Sin datos contables reales todavía.** Se probó de punta a punta con los archivos sintéticos de `docs/ejemplos/` (carga, revisión previa, controles, pantallas).
- Funciones añadidas tras el despliegue: calendario con ICA, ReteICA y exógenas; selector de año y mes; semáforo (rojo vencida, naranja por vencer, azul presentada sin pago, verde cumplida); bloques de vencidas y próximas en el tablero (ventana `ALERTA_PANTALLA_DIAS`, hoy 30); invitación de usuarios y recuperación de contraseña por correo; correos HTML con logo y resumen semanal de pendientes (lunes 7:00) a `ventas2@` y `gerencia@`; revisión previa de archivos cargados (`docs/validacion_de_cargas.md`); asistente de IA conversacional (apagado hasta poner `ANTHROPIC_API_KEY`); logo, favicon y diseño del ingreso.
- Decisiones del dueño: una instalación por empresa (no multiempresa); sin S3; copia de seguridad en el PC (pendiente); asistente de IA apagado hasta terminar las pruebas; fechas laborales (cesantías y primas) se dejan **pendientes tal como están**; exógena DIAN AG 2025 presentada.
- Lectores de exportes reales (`empresa/lectores_reales.py`, probados con los archivos reales de septiembre 2026, sin versionarlos): balance de World Office con terceros (1.072 filas de detalle, 909 ignoradas, débitos = créditos = 446.076.488,25, totales cuadran); libro auxiliar jerárquico (693 movimientos en 113 cuentas, mismo total que el balance, saldos iniciales y filas «Total» ignoradas pero usadas para validar); extracto de Bancolombia en PDF (113 movimientos; valida el encadenamiento de saldos y el resumen). El desplegable «Perfil de mapeo» de Nueva carga muestra solo perfiles del tipo elegido y el servidor rechaza perfiles de otro tipo.
- Pantallas (9-oct-2026, tras cargar datos reales): cifras con formato legible en Renta/ICA e Indicadores (`cifra` y `etiqueta` en `empresa/templatetags/utiles.py`); conciliación bancaria con selector de la cuenta contable del banco, explicación y tarjetas de resumen (con los archivos de septiembre concilian 44 movimientos y el neto del extracto coincide con libros: −11.425.822); cartera y proveedores se agrupan por nombre cuando el auxiliar no trae NIT; barra de menú fija al desplazarse.
- Facturas vs contabilidad (9-oct-2026): World Office registra su propio consecutivo («(DTS) FV FE 11407», «(DTS) FC DHT 1315»), no el número de la factura de la DIAN; por eso salían todas «sin causar». Ahora se busca el número dentro del documento o la descripción y, si no está, por tercero + valor (±$5, ventana de fechas, un asiento por factura); el valor causado se suma por documento y excluye el anticipo de retención (1355). Con septiembre: ventas 37/37 y compras 25/28 causadas (3 realmente sin causar: 2 de Finesa y 1 de HDI); parámetros `CAUSACION_*`. Los hallazgos ahora traen «Qué hacer» y un botón a la pantalla donde se corrige (`controles/acciones.py`).
- Hallazgos (9-oct-2026): con los archivos reales de septiembre salían 81 (50 de TER002 por dirección/ciudad/tipo de persona, 20 de INT003, 9 de facturas, 2 de exógena). Cambios: los controles de exógena (TER002, EXO001, EXO002) solo se evalúan cuando hay auxiliares de los 12 meses del año (`NoAplica` en el motor cierra lo abierto con ese motivo); INT003 exime cuentas contra (parámetro `PUC_CUENTAS_CONTRA`: 1299, 1399, 1499, 1592, 1597, 1599, 4175, 2408); la bandeja muestra por defecto solo los abiertos y un resumen. Quedan 17. Pendiente: el auxiliar de World Office no trae NIT (solo el nombre del tercero), y la exógena necesita NIT, dirección y ciudad: hace falta exportar el maestro de terceros de World Office e importarlo.
- Plan de cuentas real (9-oct-2026): el balance entregado por el contador dio las cuentas de World Office; `PLAN_DE_CUENTAS` en `cargar_datos_iniciales` llena los parámetros PUC (IVA 240801/240802, retenciones 2365/2367, caja y bancos 1105/1110/1120, cartera 1305, cuentas por pagar 22/2335, provisiones laborales 25/2610, etc.) sin pisar lo que alguien ya editó o verificó. Quedan por verificar con el contador: PUC_COSTOS (¿la clase 7 es costo de ventas?), PUC_ACTIVO_CORRIENTE, PUC_PASIVO_CORRIENTE (¿las obligaciones financieras 21 vencen en menos de un año?), PUC_ACTIVOS_FIJOS, PUC_NO_DEDUCIBLES y PUC_IMPUESTO_RENTA (no hay cuentas de la clase 54). IVA004 ahora reconoce los documentos de World Office vinculados a facturas recibidas. Menú hamburguesa en celular y tableta (≤ 900 px).
- Guías: `docs/guia_de_pruebas.md` (qué hace cada pantalla), `docs/arranque_con_datos_reales.md` (cómo empezar con datos reales), `docs/correo_smtp.md`, `docs/asistente_ia.md`, `docs/escalabilidad_y_empresas.md`.
- Rama de trabajo: `claude/document-review-sd30p4`, reiniciada desde `main` tras cada merge.

## Datos confirmados con el certificado de la Cámara de Comercio (expedido 1-sep-2026)
- Matrícula mercantil de la sociedad renovada el **29-abr-2026** (último año renovado: 2026); los establecimientos DH LAPTOP STORAGE y DH BOOKS también figuran renovados 2026. El plazo legal general es el 31-mar: la renovación fue posterior; si hubo sanción o un plazo distinto, confirmar con la Cámara.
- **Grupo NIIF III** y tamaño **microempresa** (ingresos por actividad ordinaria reportados en RUES: $1.626.389.817, muy por debajo del tope de IVA bimestral ≈ $4.581 millones): consistente con IVA cuatrimestral. El Grupo 3 usa el marco simplificado para microempresas del Decreto 2420 de 2015: revisar con el contador qué estados e indicadores aplican.
- CIIU: principal 4651, secundaria 4923, otras 5320 y **5210**. El RUT listaba 5320 y 9511: **discrepancia por aclarar** (afecta tarifa de ICA).
- Inscrito en el RIT (Bogotá) desde el 3-ene-2017.
- Los datos personales del certificado (documentos de identidad) no se guardan en el repositorio.

## Estado del calendario (decisión del dueño, 9-oct-2026)
Todos los impuestos con vencimiento **hasta el 9-oct-2026** (retefuente, IVA, ICA) se marcan "presentada y pagada", sin evidencia cargada. Solo queda pendiente la **retención de septiembre, vence el 22-oct-2026** (Ideako). `CONTROL_DESDE = 2026-10-01`: lo anterior no genera alertas. Fechas laborales (cesantías, prima): el dueño decidió dejarlas pendientes tal como están (9-oct-2026), aunque hoy no haya contratos; alertan hasta marcarlas como cumplidas.

## Historial del CI (qué falló y por qué)
| Corrida | Commit | Resultado | Causa | Solución |
|---|---|---|---|---|
| 1 | `899989f` (rama) | ❌ ruff | Imports sin ordenar en archivos nuevos | Corregido con `ruff --fix` en `be7249d` |
| 2 y 3 | `be7249d` (rama y PR) | ✅ | — | — |
| 4 | `bb37121` (`main`, tras el merge) | ❌ pytest contra PostgreSQL | Prueba inestable `test_flujo_de_carga_y_vigencia`: generaba el `.xlsx` dos veces y el archivo lleva marca de tiempo, así que a veces los bytes (y la huella) diferían y no se detectaba el duplicado. Error de la prueba, no del producto | Se genera el contenido una sola vez (commit de esta rama) |

Nota: el merge se hizo viendo verdes las corridas del PR; la corrida sobre `main` falló después por la prueba inestable descrita. Lección: esperar también el CI de `main` antes de dar algo por cerrado.

## Pendiente (en orden)
1. **Copia de seguridad fuera del servidor y prueba de restauración (P0)**: `docs/respaldo_en_mi_pc.md`. Obligatoria antes del primer dato real.
2. Confirmar con Ideako el plan de cuentas, los conceptos de retención, la tarifa de ICA/CIIU y quién presenta la exógena distrital (26-oct-2026); luego marcar los parámetros *Verificados*. Ver `docs/arranque_con_datos_reales.md` §2.
3. Pedir los exportes de septiembre de 2026 y hacer la primera carga real (P1–P3). El dueño puede pasar solo la fila de encabezados de cada archivo para preparar los perfiles.
4. Cambiar la contraseña del buzón SMTP si aún no se hizo en el `.env` del servidor (se compartió en un chat).
5. Encender el asistente de IA tras P1 y P2 (clave en el `.env`, con tope de gasto).
6. Mejoras fuera del MVP: vendorizar Chart.js, importación asíncrona, invitaciones con más control, API.

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
