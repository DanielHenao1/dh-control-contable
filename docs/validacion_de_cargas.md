# Revisión previa de los archivos que se suben

Antes de guardar un archivo, el sistema revisa que sea del tipo, la empresa y el periodo que eligió quien lo sube. Son heurísticas sobre el contenido, no una garantía: un archivo escaneado o con columnas de otro formato solo puede generar un aviso. La revisión del contador sigue siendo necesaria.

## Qué revisa
| Revisión | Resultado si falla |
|---|---|
| Extensión según el tipo (Excel/CSV, XML o .zip, PDF) | **Error**: no se guarda |
| El archivo se puede leer y tiene filas | **Error** |
| Las columnas corresponden a otro tipo (por ejemplo, un balance subido como auxiliar) | **Error** que dice a qué tipo se parece |
| No reconoce las columnas del tipo elegido | Aviso: habrá que mapearlas a mano |
| Facturas: ninguna es del NIT de la empresa | **Error** (archivo de otra empresa) |
| Facturas: «emitidas» marcado con compras, o al revés | **Error** |
| Las fechas son en su mayoría de otro periodo | Aviso |
| Declaración PDF: formulario elegido distinto al del PDF (300 = IVA, 350 = retención en la fuente, 110 = renta) | **Error** |
| Declaración PDF: no aparece el número del formulario, el NIT o la palabra clave | Aviso |
| PDF escaneado o cifrado (sin texto legible) | Aviso: no se pudo verificar |
| Mismo archivo ya cargado (huella SHA-256) | Se redirige al ya cargado |

## Quién puede subir pese a un error
Solo el dueño (permiso «administrar»), marcando «Subir de todas formas». Queda en la auditoría como `carga_forzada` y en el detalle del archivo. El asistente de carga y los demás roles no pueden forzar.

## Facturas de varios meses
Una carga normal asigna todo el archivo a **un** periodo. Para facturas electrónicas que abarcan varios meses (por ejemplo, de enero a septiembre) marca **«El archivo trae varios meses: repartir las facturas por su fecha de emisión»** y elige como periodo el **último mes** del rango. Al confirmar, cada factura queda en el mes de su fecha y se recalculan los controles de todos los meses tocados.
Reglas para no duplicar:
- Un archivo de varios meses reemplaza solo a otro de varios meses con el mismo mes final y sentido; un archivo mensual no lo reemplaza.
- Si ya hay facturas de un mes en otro archivo vigente, la confirmación se rechaza con un mensaje: usa o un archivo de varios meses o archivos mensuales para ese rango, no ambos.
- Un mes **cerrado** no admite facturas nuevas.
- Solo aplica a facturas (Excel DIAN y XML/zip).

## Libro de facturas de la DIAN (una hoja por mes)
El Excel que baja la DIAN trae las facturas **emitidas y recibidas juntas**, una hoja por mes y una columna **Grupo** (Emitido/Recibido). Para cargarlo:
1. Cargas → Nueva carga → «Facturas electrónicas (Excel DIAN)».
2. Perfil: **«DIAN · libro de facturas (una hoja por mes)»** (viene creado: lee todas las hojas, usa Folio como número, Fecha Emisión en formato día-mes-año, Estado como estado DIAN y Grupo como sentido).
3. Deja el sentido vacío (lo toma de la columna Grupo), marca **«El archivo trae varios meses»** y elige como periodo el último mes (septiembre de 2026).
Detalles:
- Una hoja sin encabezado (por ejemplo, con la primera fila borrada) reutiliza el encabezado de la hoja anterior si tiene las mismas columnas.
- **No son facturas y se omiten** (se cuentan en el resumen de la carga como «no_son_facturas_omitidas»): acuses de recibo (*Application response*), nómina electrónica individual y notas de ajuste del documento soporte.
- Los *documentos soporte* (compras a no obligados a facturar) quedan como documento soporte emitido y no entran al IVA, como ya lo hacían las reglas.
- Si todas las filas son de otra empresa se rechaza; si algunas no coinciden con su columna Grupo o con el NIT, avisa.

## Avisos
Se muestran al subir y quedan en el detalle del archivo («Avisos de la revisión previa»).

## Límites conocidos
- No se conocen los formatos reales de las exportaciones de World Office, por eso el reconocimiento de columnas usa los nombres de los campos y puede no reconocer un formato propio; en ese caso se mapea con un perfil.
- En el PDF de la DIAN no se verifica el periodo: el orden del texto extraído no es confiable.
- Se revisan las primeras 500 filas.
