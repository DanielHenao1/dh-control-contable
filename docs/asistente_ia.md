# Asistente de IA

Pantalla **Asistente** (menú, solo dueño y contador): chat que responde preguntas con los datos que el sistema ya calculó. Además redacta la explicación de cada hallazgo.

## Qué ve la IA y qué no
- Ve un resumen de solo lectura: obligaciones del año (fecha, estado, fuente), hallazgos abiertos (regla, norma, título y detalle minimizados), últimas cargas y parámetros vigentes.
- **No** recibe NIT, correos ni números largos de identificación (se reemplazan por `[NIT]`, `[correo]`, `[ID]`), tampoco el NIT de la empresa. Las preguntas también se minimizan antes de enviarse.
- No consulta la base de datos por su cuenta: solo ve el resumen que arma el sistema (`asistente/contexto.py`).
- **No calcula** impuestos, retenciones ni sanciones y no inventa fechas ni normas; si el dato no está, lo dice. Los cálculos viven en `impuestos/reglas/` y `controles/reglas_*.py`.
- Cada pregunta queda en la auditoría (`ia_pregunta`) con el texto minimizado; los fallos como `ia_error`. La respuesta no se guarda; la conversación vive en la sesión (se pierde al cerrar sesión o al pulsar «Nueva conversación»).

## Límites
30 preguntas por usuario y hora (`ASISTENTE_PREGUNTAS_POR_HORA`), 500 caracteres por pregunta, respuestas de hasta 600 tokens, historial de las últimas 6 preguntas.

## Activarlo
1. Crear una clave de API en la consola de Anthropic (console.anthropic.com) y fijar un tope de gasto mensual allí.
2. En el servidor, solo en el `.env` (nunca en el repositorio ni en el chat): `ANTHROPIC_API_KEY=<clave>`. El modelo es `ASISTENTE_MODELO` (por defecto `claude-sonnet-5-5`).
3. Recrear los contenedores: `cd /opt/control && docker compose up -d --force-recreate web worker beat`.
4. Probar en `/asistente/`. Sin clave, la pantalla avisa que está apagado y los hallazgos usan la redacción local.

## Privacidad
Con la clave activa, el resumen minimizado y la pregunta salen del servidor hacia la API de Anthropic. Si cambia la política de la empresa, basta con quitar `ANTHROPIC_API_KEY` y recrear los contenedores.
