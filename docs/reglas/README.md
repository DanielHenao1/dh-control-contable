# Reglas de control y su fuente

Cada regla vive en `controles/reglas_*.py` (registro con `@regla`) y se lista en la app en **Hallazgos → Catálogo**. Los cálculos de los borradores viven en `impuestos/reglas/`. **Verifica cada norma con el contador antes de apoyarte en ella**: aquí se anota la fuente que cita el código.

| Regla | Qué verifica | Fuente que cita |
|---|---|---|
| INT001–INT006 | Partida doble, saldo calculado vs reportado, naturaleza contraria, periodo sin carga, asiento descuadrado, documento duplicado | Principio de partida doble (Decreto 2420 de 2015, marco técnico) |
| TER001–TER004 | DV (módulo 11), datos mínimos de exógena, tercero fuera del maestro, duplicados | Estatuto Tributario art. 555-1; resolución DIAN de exógena |
| FAC001–FAC006 | Factura sin causar, valor distinto, duplicada, nota crédito sin vínculo, fecha fuera de periodo, saltos de numeración | Estatuto Tributario art. 771-2; autorización de numeración DIAN |
| IVA001–IVA004 | FE vs contabilidad, propio vs declarado, periodicidad (92.000 UVT), descontable sin soporte | Estatuto Tributario arts. 488, 600, 771-2 |
| RET001–RET006 | Retenido vs teórico (base en UVT × tarifa por concepto y condición del tercero), base mínima, tarifa, concepto sin tarifa, pagos vs contabilidad vs declarado | Estatuto Tributario art. 365 y ss.; Decreto 1625 de 2016 |
| REN001–REN004 | Diferencias sin explicar, tasa mínima (referencial), gastos sin soporte, no deducibles | Estatuto Tributario arts. 107, 115, 240 par. 6, 772-1; Decreto 1998 de 2017 |
| EXO001–EXO002 | Terceros reportables sin datos, facturas vs auxiliares | Resolución DIAN de exógena del año gravable |
| CAL001–CAL005 | Vencimientos, responsables, evidencia, revisión anual del calendario, fechas sin verificar | Decreto 2229 de 2023; Resolución SDH-000195 de 2025 (ICA Bogotá) |

## Calendario
Las fechas nacionales salen de la regla “día hábil n según el último dígito del NIT” (Decreto 2229 de 2023) y la tabla de festivos (Ley 51 de 1983 + Semana Santa, calculada). Para el dígito 9 solo está confirmado el día hábil 15. Cada diciembre se contrastan con el calendario oficial de la DIAN (`python manage.py verificar_calendario` lista lo que aún no tiene dos fuentes).

## Cómo agregar una regla
1. Crear la función en `controles/reglas_<grupo>.py` con `@regla(codigo, grupo, nombre, severidad, norma)` que devuelva una lista de `Resultado` (o `None` si no aplica al periodo).
2. Documentarla en esta tabla con su fuente.
3. Escribir pruebas con datos sintéticos en `tests/`.
