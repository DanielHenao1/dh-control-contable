# DH TRANS-STORAGE — Sistema de control contable

## Qué es
Aplicación Django + PostgreSQL que verifica la contabilidad llevada en World Office. No registra ni causa, y no presenta declaraciones.

## Datos confirmados de la empresa
- DH TRANS-STORAGE SAS, NIT 900.902.549-7 (termina en 9), domicilio en Bogotá.
- Contabilidad en World Office instalado en servidor propio, sin API: la entrada es por exportes Excel/CSV.
- Contratista contable: Ideako (contrato CT-0029-2026). El sistema es una segunda verificación independiente.
- IVA cuatrimestral. ICA de Bogotá bimestral (inferido; confirmar): el 4.º bimestre de 2026 ya está declarado y pagado.
- Retención en la fuente mensual: la de septiembre vence el 22-oct-2026, está pendiente de presentar y está incluida en el servicio de Ideako.
- UVT 2026 = $52.374. Va como parámetro con vigencia, nunca fija en el código.

## Reglas obligatorias
- Los cálculos tributarios son deterministas y viven en `impuestos/reglas/` (y las reglas de control en `controles/reglas_*.py`). La IA nunca calcula.
- Ningún parámetro tributario (UVT, tarifas, bases, fechas, festivos, periodicidad) va fijo en el código: se guarda en tablas con fecha de vigencia (`empresa.Parametro`, `impuestos.ConceptoRetencion`, `impuestos.TarifaICA`, `calendario.ReglaVencimiento`, `calendario.Festivo`).
- Cada regla cita su norma en `docs/reglas/` y tiene pruebas con casos anonimizados.
- Los archivos cargados no se sobrescriben: se guardan con huella (hash).
- Todo cambio de datos escribe en `RegistroAuditoria`.
- Nunca hay datos reales ni secretos en el repositorio.
- Si falta un dato o una norma, se pregunta o se marca como pendiente; nunca se inventa.
- La interfaz va en español colombiano.

## Definición de terminado
Pruebas pasando (`pytest`), `ruff check` limpio, regla documentada con su fuente, migraciones, auditoría y revisión básica de seguridad.

## Comandos
- Pruebas: `pytest` · Estilo: `ruff check .`
- Datos iniciales: `python manage.py cargar_datos_iniciales`
- Ver `README.md` (local) y `docs/despliegue.md` (VPS).

## Continuidad entre sesiones
- Antes de trabajar, leer `docs/ESTADO_PROYECTO.md` (dónde vamos, qué falló, qué sigue), `docs/PROGRESO.md` y `docs/decisiones.md`. Al terminar, actualizar `docs/ESTADO_PROYECTO.md`.
- Despliegue: `docs/plan_despliegue_hostinger.md` (plan y diagnóstico) y `docs/despliegue.md` (comandos). No ejecutar despliegues, tocar servidores ni pedir o mostrar contraseñas sin aprobación explícita del usuario.
- No dar un cambio por cerrado hasta ver verde el CI de la rama **y** el de `main` tras el merge.
