# Régimen de renta y parámetros de renta

**Régimen:** ordinario. El RUT (actualización del 15-abr-2025, impreso el 17-jul-2026) trae en la casilla 53 la responsabilidad 05 (impuesto de renta y complementarios, régimen ordinario) y no trae la 47 (Régimen Simple de Tributación). Además: 07 (retención en la fuente a título de renta), 09 (retención en la fuente en el impuesto sobre las ventas), 14 (informante de exógena), 42 (obligado a llevar contabilidad), 48 (IVA), 52 (facturador electrónico) y 55 (informante de beneficiarios finales). Persona jurídica, dirección seccional Impuestos de Bogotá.

| Parámetro | Valor | Norma |
|---|---|---|
| `RENTA_TARIFA` | 0,35 | Estatuto Tributario art. 240 (tarifa general de sociedades, Ley 2277 de 2022) |
| `RENTA_TASA_MINIMA` | 0,15 | Estatuto Tributario art. 240 par. 6 (tasa mínima de tributación) |
| `RENTA_ANTICIPO_PORCENTAJE` | 0,75 (por verificar) | Estatuto Tributario art. 807: 25 % el primer año, 50 % el segundo y 75 % desde el tercero; la empresa declara desde 2015. Las fuentes consultadas no son la versión oficial vigente: confirmar con la contadora |
| `IVA_TOPE_BIMESTRAL_UVT` | 92.000 | Estatuto Tributario art. 600 |

**Pruebas:** `tests/test_analitica.py` (parámetros verificados tras `cargar_datos_iniciales`).
