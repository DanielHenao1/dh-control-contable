# Borrador del formulario 350 · Retención en la fuente

**Qué es:** un borrador propio, armado con el balance y los auxiliares del mes, para contrastarlo con la declaración que presenta el contratista. No se presenta desde el sistema. Código: `impuestos/reglas/formulario_350.py`.

## Fuentes
- Estructura de casillas (conceptos, base y retención, personas jurídicas y naturales, autorretenciones): formulario 350 de una declaración presentada (agosto de 2026). Confirmar contra el formulario vigente cuando la DIAN lo cambie.
- Aproximación de valores al múltiplo de mil más cercano: Estatuto Tributario art. 577. Los totales (casillas 130, 136) suman las casillas ya aproximadas.
- Plan de cuentas: subcuentas 2365 del balance de World Office (septiembre de 2026), cuyos nombres traen la tarifa («HONORARIOS DECLARANTES 11%»).

## Reglas
1. **Retención practicada del mes** = créditos del mes de las cuentas de retención (`PUC_RETEFUENTE`, 2365). Los débitos son el pago de la retención del mes anterior a la DIAN y no se restan.
2. **Concepto** de cada subcuenta: parámetro `RETEFUENTE_MAPA_CUENTAS` (prefijo de cuenta = concepto del formulario). Las cuentas sin concepto se muestran en «Otros pagos» con una advertencia.
3. **Base** = retención ÷ tarifa, con la tarifa tomada del nombre de la subcuenta. Sin tarifa en el nombre, la base queda en 0 con advertencia.
4. **Personas jurídicas o naturales:** según cada movimiento del auxiliar: tipo de persona del maestro de terceros; si falta, por el NIT (9 dígitos que empiezan por 8 o 9 = jurídica; cédula = natural), con advertencia. Sin auxiliar, todo se muestra como jurídicas.
5. **Retenciones de IVA** (casilla 131): créditos del mes de `PUC_RETEIVA`.
6. Quedan para diligenciar a mano: retenciones en exceso o anuladas (129), timbre (135), sanciones (137) y el pago.

## Cómo se obtiene
Cargar el balance y el libro auxiliar del mes (y el maestro de terceros). En Impuestos → Retención en la fuente: «Ver y descargar borrador del formulario 350» (pantalla, PDF y Excel; las descargas piden permiso de exportar y quedan en la auditoría).

## Pruebas
`tests/test_formulario_350.py`: cifras inventadas con la misma estructura de una declaración presentada (honorarios, arrendamientos, rendimientos y autorretenciones de ventas y servicios por tipo de persona; el total coincide con la suma de casillas).
