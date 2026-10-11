# Borrador del formulario 302 · ICA, avisos y tableros (Bogotá)

**Qué es:** un borrador propio, armado con los balances de los dos meses del bimestre, para contrastarlo con la declaración que presenta el contratista. No se presenta desde el sistema. Código: `impuestos/reglas/formulario_302.py`.

## Fuentes
- Estructura de renglones (9 a 27) y su encadenamiento: formulario 302 de la Secretaría Distrital de Hacienda, tomado de la declaración presentada del 4.º bimestre de 2026. El renglón 18 dice «15 % del renglón 17» y el 23 cita el Acuerdo 780 de 2020.
- Tarifas por mil: las subcuentas de retención de ICA de World Office traen la tarifa en el nombre («… VENTA DE PRODUCTOS 11,04», «… VENTA DE SERVICIOS 9,66») y cuadran con la declaración presentada (4651: 11,04; 6399: 9,66). Quedan **por verificar** con la tabla de tarifas del Distrito (Acuerdo 65 de 2002).
- Aproximación al múltiplo de mil más cercano: Estatuto Tributario art. 577.

## Reglas
1. **Ingresos del bimestre** = créditos − débitos de las cuentas de ingreso (`PUC_INGRESOS`) en los balances de los dos meses (renglón 9). Las devoluciones (`ICA_CUENTAS_DEVOLUCIONES`, 4175) salen en el renglón 12.
2. **Actividad de cada ingreso:** parámetro `ICA_MAPA_INGRESOS` (prefijo de cuenta = `principal`, un CIIU o `ignorar`; gana el prefijo más largo). Por defecto todo va a la actividad principal.
3. **Datos manuales** (`AjusteICA`, «Datos manuales del bimestre»): ingresos fuera del Distrito (10), exportaciones (13), venta de activos fijos (14), deducciones y no sujetas (15), unidades adicionales (19), sanciones (22), descuento tributario (23) e intereses de mora (26). Los renglones 10, 13, 14 y 15 se restan de la actividad principal.
4. **Base por actividad:** las secundarias se aproximan a miles; la principal es lo que falta para sumar el renglón 16.
5. **ICA (17)** = Σ base × tarifa por mil de cada actividad, aproximado a miles. **Avisos y tableros (18)** = `ICA_AVISOS_PORCENTAJE` (15 %) del renglón 17 aproximado.
6. **Retención de ICA que le practicaron (21)** = débitos − créditos del bimestre de las cuentas de `ICA_CUENTAS_RETENCION_SUFRIDA` (135518). La ReteICA que la empresa practica a sus proveedores se declara aparte.
7. **Saldo (24)** = 20 − 21 + 22 − 23. Si es negativo hay saldo a favor y el valor a pagar es 0.

## Cómo se obtiene
Cargar los balances de los dos meses del bimestre. En Impuestos → ICA: «Ver y descargar borrador del formulario 302» (pantalla, PDF y Excel; las descargas piden permiso de exportar y quedan en la auditoría). Si falta un balance, el borrador lo avisa.

## Pruebas
`tests/test_formulario_302.py`: cifras inventadas con la misma estructura de una declaración presentada (ICA por dos actividades, devoluciones, ingresos fuera de Bogotá, avisos y tableros, retención sufrida y saldo a pagar).
