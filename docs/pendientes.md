# Qué falta validar con tus datos reales y con el contador

El sistema está construido con datos sintéticos. Cada fase del plan termina en una puerta que exige datos reales.

## Puertas de calidad (no se pueden cerrar sin ti)
- **P0** — Desplegar en el VPS con HTTPS y doble factor, y **restaurar una copia completa** (`docs/despliegue.md`).
- **P1** — Importar el balance de un mes real de World Office: crear el perfil de mapeo (Cargas → Ajustar mapeo) y verificar que los totales cuadran con World Office. Confirmar dos convenciones que **asumí**: (a) el saldo final viene positivo en la naturaleza de la cuenta; (b) Débitos/Créditos son del mes y el saldo de resultados es acumulado del año (`docs/decisiones.md`, punto 5).
- **P2** — IVA y retención de un mes real coinciden con lo declarado o cada diferencia queda explicada. Importar las facturas DIAN reales (Excel y/o XML) y los pagos con retención.
- **P3** — Compartir el primer informe mensual con Ideako; revisar el calendario con las fechas verificadas.
- **P4** — Contrastar con el contador los borradores de renta, ICA y exógena y la proyección de un cierre de prueba; documentar cada supuesto.

## Parámetros que debe aportar o confirmar el contador (Configuración)
El tablero muestra un aviso mientras haya parámetros “por verificar” o vacíos.
1. **Conceptos de retención** con base mínima en UVT y tarifas (declarante / no declarante): no se cargó ninguno.
2. **Tarifa de ICA** de la actividad principal en Bogotá y periodicidad bimestral (se infiere del 4.º bimestre ya declarado). Verificar las descripciones exactas de los CIIU 4651, 4923, 5320 y 9511.
3. **Prefijos de cuentas del plan real** (`PUC_*`): IVA generado y descontable (el plan menciona la 2408), retefuente, ReteIVA, caja, cartera, proveedores, activo y pasivo corriente, gastos no deducibles. Hoy están con el PUC comercial estándar o vacíos.
4. **Renta:** tarifa (cargada 35 % “por verificar”), tasa mínima (15 %, referencial), porcentaje de anticipo (vacío), diferencias contable-fiscal.
5. **Exógena:** topes por tercero de la resolución del año gravable.
6. **UVT 2027** cuando se publique (UVT 2025 está “por verificar”).
7. **Reglas de vencimiento** de otros dígitos del NIT solo si cambia la empresa; hoy solo existen las del dígito 9.
8. **Formulario de ReteIVA** (código 09 del RUT), quién firma cada declaración y si el RUT necesita actualización.
9. **Beneficiarios finales (RUB)** y **exógena**: fecha y norma (el sistema las deja “sin verificar” a propósito).
10. **CIIU:** el certificado de la Cámara dice 5210 donde el RUT decía 9511; aclarar cuál es el correcto. **Grupo NIIF III (microempresa):** confirmar con el contador qué estados e indicadores del sistema aplican.
11. **Usuario aduanero (código 23)** y si hay comercio exterior.
12. **Exógena:** (a) ¿se presentó la de la DIAN año gravable 2025 (vencía el 28-may-2026)? (b) La distrital de Bogotá AG 2025 vence el **26-oct-2026**: confirmar quién la presenta (¿está dentro del contrato con Ideako?) y que la empresa está obligada. Verificar las fechas en los textos oficiales (Res. DIAN 000227 de 2025 y Res. SDH DDI-024115 de 2026).
12b. **Otros impuestos y obligaciones por confirmar si aplican:** impuesto predial y vehicular de Bogotá (¿inmuebles o vehículos a nombre de la empresa?), informes a la Superintendencia de Sociedades (la empresa está vigilada), exógena nacional y distrital (fechas por resolución), sobretasa bomberil (solo ingresos altos) y el formulario donde se declara la ReteIVA. Se agregan cuando se confirme que aplican y con fuente.
13. **Fechas laborales** (cesantías, prima): decisión del dueño (9-oct-2026): se dejan pendientes tal como están en el calendario.
14. **Por escrito con Ideako:** que la retención de septiembre (22-oct-2026) está dentro del servicio, y el acuse del ICA del 4.º bimestre ya pagado.

## Cosas que probar con archivos reales
- Formatos de las facturas DIAN (Excel y XML/AttachedDocument) y de los auxiliares de World Office.
- Rendimiento con un año completo de auxiliares (si es lento, mover la importación a Celery).
- Reglas con muchos falsos positivos (`/hallazgos/catalogo/`): se pueden desactivar o ajustar severidad en el administrador.

## Mejoras fuera del MVP
- Vendorizar Chart.js (hoy se carga de un CDN con versión fija).
- Importación asíncrona con barra de progreso.
- API (el plan la menciona si más adelante se necesita React).
