# Decisiones tomadas durante la construcción

Registradas sin esperar aprobación (el plan pidió trabajo autónomo). Cada una se puede revertir.

1. **Python 3.12 en Docker; el desarrollo corrió en 3.13.** El código no usa nada exclusivo de una versión.
2. **SQLite en desarrollo y pruebas, PostgreSQL en producción** (`DATABASE_URL`). CI corre las pruebas contra PostgreSQL.
3. **Apps en la raíz del repositorio** (una carpeta por app, como pide el plan). Se añadió el modelo `Usuario` (roles), `Parametro`, `PerfilImportacion`, `ArchivoCargado` y `RegistroAuditoria` a la app `empresa`.
4. **Roles:** dueño/administrador, contador (lectura y gestión de hallazgos, simulador, exportación), asistente (cargas), consulta y contratista (solo su pantalla). Es la unión de los roles del plan y del primer prompt.
5. **Importadores por perfiles de mapeo configurables** (no se conocen los formatos reales). Convención asumida del balance: el saldo final viene positivo en la naturaleza de la cuenta (activos/gastos débito, pasivos/ingresos crédito) y las columnas Débitos/Créditos son del mes; el saldo de resultados es acumulado del año. **Validar con exportes reales (puerta P1).**
6. **Importación síncrona en la petición web** (archivos mensuales pequeños). Los controles se recalculan en Celery (`controles.tasks`), que en desarrollo corre en modo inmediato.
7. **Vigencia de cargas:** el último archivo importado por tipo/periodo/sentido es el "vigente"; los anteriores se conservan, nunca se borran. Facturas Excel y XML cuentan como el mismo tipo.
8. **Calendario por regla.** Solo existen reglas verificadas en el plan (NIT terminado en 9 → día hábil 15 para retención, IVA y renta). Otros dígitos quedan sin fecha y con aviso; no se inventaron. Los festivos se calculan (Ley 51/1983 + Semana Santa) y se pueden corregir a mano. Las fechas de ICA Bogotá son fijas y de una sola fuente secundaria (marcadas así).
9. **Verificación visible:** cada obligación guarda su nivel de verificación (dos fuentes, una fuente, regla, estimada, no verificada). Solo las confirmadas en el plan figuran como "dos fuentes".
10. **Parámetros "por verificar".** Se cargan con valor sugerido o vacío (p. ej. tarifa de renta 35 %, prefijos PUC, tasa mínima) con aviso permanente en pantalla. Las tarifas de retención, ICA y topes de exógena **no se cargaron**: el contador debe aportarlas.
11. **Retención teórica:** base mínima en UVT × UVT vigente del año del pago; tarifa según condición del tercero (declarante o no).
12. **Renta y tasa mínima** son referenciales: la fórmula legal de tasa mínima usa utilidad depurada que el sistema no tiene; se compara la tasa efectiva estimada. El anticipo queda pendiente hasta que el contador defina el parámetro.
13. **Proyección:** promedio estacional escalado (si hay año anterior) o suavizado exponencial simple; banda de ±1,96 desviaciones. Escenarios favorable/adverso = extremos de la banda. Caja proyectada = lineal sobre los últimos 3 meses (referencial).
14. **Asistente de IA opcional** (`ANTHROPIC_API_KEY`). Recibe solo hallazgos ya calculados con identificadores removidos; sin clave redacta con plantilla local. No calcula.
15. **Frontend:** plantillas Django + CSS propio (paleta azul marino y gris) + Chart.js desde CDN con versión fija. HTMX y Tailwind no se usaron: no hacían falta para el MVP y evitan una cadena de compilación. Para producción estricta se puede vendorizar Chart.js.
16. **PDF** con WeasyPrint; si faltan las librerías del sistema se entrega HTML imprimible.
17. **Doble factor** TOTP (django-otp) con 8 códigos de recuperación; bloqueo de intentos por usuario+IP (caché) además de fail2ban en el servidor.
