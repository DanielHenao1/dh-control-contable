# Archivos de ejemplo (sintéticos)

Datos inventados de **septiembre de 2026** para probar el sistema de punta a punta. Nada de esto es información real: los terceros son ficticios y las cifras están hechas para que el sistema encuentre diferencias a propósito. Se usa el NIT de la empresa solo para que pase la revisión de «¿es de esta empresa?».

| Archivo | Tipo al subirlo | Notas |
|---|---|---|
| `balance_2026-09.csv` | Balance de prueba | Débitos = créditos (24.613.000) |
| `auxiliar_2026-09.csv` | Auxiliares | Compras, ventas, recaudo y pago a proveedor |
| `facturas_recibidas_2026-09.csv` | Facturas electrónicas (Excel DIAN) → **Recibidas** | 4 compras |
| `facturas_emitidas_2026-09.csv` | Facturas electrónicas (Excel DIAN) → **Emitidas** | 3 ventas (falta la 503 a propósito) |
| `retenciones_2026-09.csv` | Retenciones practicadas | 2 retenciones de compras |
| `extracto_banco_2026-09.csv` | Extracto bancario | Incluye un cargo bancario que no está en libros |

Diferencias sembradas a propósito y el hallazgo que debe aparecer: ver `docs/guia_de_pruebas.md`, paso 5.
