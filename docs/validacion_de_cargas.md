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

## Avisos
Se muestran al subir y quedan en el detalle del archivo («Avisos de la revisión previa»).

## Límites conocidos
- No se conocen los formatos reales de las exportaciones de World Office, por eso el reconocimiento de columnas usa los nombres de los campos y puede no reconocer un formato propio; en ese caso se mapea con un perfil.
- En el PDF de la DIAN no se verifica el periodo: el orden del texto extraído no es confiable.
- Se revisan las primeras 500 filas.
