# Cómo empezar a trabajar con datos reales

Hoy el sistema está desplegado y **no tiene ningún dato contable** (no hay nada que borrar). Los archivos de `docs/ejemplos/` ya se probaron de punta a punta en una copia de pruebas, así que no hace falta repetirlos en producción. Este es el orden para pasar a datos reales sin riesgos.

## 1. Primero la copia de seguridad (puerta P0, obligatoria)
Nada real entra antes de esto. Ahora es el mejor momento para probar la restauración, porque la base está casi vacía y restaurar no pierde nada.
1. Seguir `docs/respaldo_en_mi_pc.md` pasos 0 a 5: copia diaria en el servidor (3:15 a. m., ya programada), llave dedicada, traerla a tu PC y programar la descarga.
2. **Probar la restauración** (paso 6 del mismo documento): `./deploy/restore.sh <copia>` y entrar a verificar que todo sigue ahí.
3. Guardar la `BACKUP_PASSPHRASE` en tu gestor de contraseñas. Sin ella la copia no se abre.

## 2. Configurar los parámetros (sin depender de Ideako)
Mientras estos datos estén «por verificar», el tablero lo avisa y los cálculos que dependen de ellos salen marcados. Los valores ya están en tu World Office y en tus documentos; los llenas tú en Configuración y los marcas *Verificados*:
- **Cuentas** (IVA generado y descontable, retención 2365, ReteIVA 2367, bancos, cartera, proveedores, activo y pasivo corriente): del plan de cuentas de World Office. Solo los códigos.
- **Conceptos de retención** con tarifa y base mínima en UVT: de la parametrización de retenciones de World Office (Renta, ICA, exógena → Conceptos).
- **Tarifa de ICA**: de la declaración del 4.º bimestre ya presentada (tarifa por mil).
- **CIIU**: el del RUT vigente de la DIAN (la Cámara de Comercio dice 5210 y el RUT 9511; si difieren, se actualiza el RUT).
Si quieres una segunda mirada, el contador puede revisarlos una vez; es opcional.

**Ideako presenta** la retención de septiembre (22-oct-2026) y la exógena distrital (26-oct-2026), según la empresa. Ambas quedan en el calendario con Ideako como responsable. Cuando las presente, pídele el **acuse**, súbelo como evidencia en la obligación y márcala presentada o pagada.

## 3. Pedir los exportes de un mes (septiembre de 2026)
A quien lleva World Office (Ideako o la empresa), en Excel o CSV:
| Archivo | Columnas que el sistema necesita (* obligatorias) |
|---|---|
| Balance de prueba | cuenta*, nombre, saldo inicial, débitos*, créditos*, saldo final* |
| Auxiliares | fecha*, comprobante, documento, cuenta*, NIT, nombre del tercero, descripción, débito*, crédito* |
| Facturas electrónicas **recibidas** y **emitidas** (Excel del portal de la DIAN, un archivo por cada sentido; o los XML en un .zip) | número*, fecha*, NIT emisor*, NIT receptor*, total*, y si vienen: tipo de documento, prefijo, CUFE, subtotal, IVA, retenciones, estado |
| Retenciones practicadas | fecha*, NIT*, concepto*, base*, retenido*, y documento y tarifa aplicada |
| Extracto bancario | fecha*, valor* (ingresos positivos, egresos negativos), descripción, referencia |
Los nombres de columna no tienen que coincidir: si no se reconocen, se mapean una sola vez y queda un perfil guardado.

**Atajo:** pásame solo la **primera fila** (los nombres de columna, sin ningún dato) de cada archivo y te dejo los perfiles listos para que la primera carga salga sin mapear a mano.

## 4. Primera carga (septiembre de 2026), en este orden
1. **Balance de prueba**. Mira la vista previa **antes** de confirmar (hasta ahí no entra nada). Confirma que los totales de débitos y créditos y 2 o 3 cuentas coinciden con World Office (puerta P1). Dos supuestos del sistema que hay que contrastar: el saldo final viene positivo en la naturaleza de la cuenta, y débitos y créditos son del mes.
2. **Auxiliares**, **facturas recibidas**, **facturas emitidas**, **retenciones** y **extracto**, uno por uno, confirmando cada importación.
3. Ir a **Hallazgos**. La primera vez habrá bastantes: unos serán errores reales, otros diferencias de formato o parámetros sin verificar. **No corrijas nada en World Office todavía**: clasifícalos con Ideako (error real, diferencia explicable, falso positivo).
4. En **IVA y retención**, comparar con lo declarado (puerta P2). Registrar la declaración presentada en Renta, ICA, exógena → Declaraciones para que el sistema la compare.
5. **Informes**: descargar el informe del mes y compartirlo con Ideako (puerta P3).

## 5. Rutina mensual (cuando ya esté en marcha)
| Cuándo | Quién | Qué |
|---|---|---|
| Primeros días del mes | Asistente de carga | Exportar de World Office y subir los 6 archivos del mes anterior; confirmar cada importación |
| Después de cargar | Dueño o contador | Revisar hallazgos, marcar explicados o corregidos, pedir ajustes a Ideako |
| Antes de cada vencimiento | Dueño | Mirar las tarjetas naranja del tablero; marcar presentada o pagada con su acuse |
| Cierre | Dueño | Pasar el periodo a «cerrado» cuando ya está revisado (no admite más cargas) |
| Cada mes | Dueño | Probar una restauración de la copia |

## 6. Cuidados con datos reales
- Los exportes se suben **directo al sistema**: no por WhatsApp ni por correo con otras claves.
- Cada persona con su usuario y su doble factor; el asistente de carga solo ve y sube.
- Nunca pegues datos reales ni contraseñas en el chat conmigo ni en GitHub.
- Confirma los parámetros como *Verificados* solo con valores que salgan de World Office o de un documento oficial (RUT, declaración presentada); ante la duda, pregunta.
- No mezcles varios meses en un mismo archivo y no uses «Otro soporte» para evitar la revisión previa.

## 7. Cuándo encender el asistente de IA
Después de pasar P1 y P2 (los datos cuadran con World Office y con lo declarado). Con tope de gasto en la consola de Anthropic. Ver `docs/asistente_ia.md`.
