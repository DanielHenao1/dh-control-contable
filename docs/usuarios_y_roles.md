# Usuarios y roles

Los usuarios los crea el dueño en **Configuración → Nuevo usuario** con su nombre, correo y rol. El sistema le envía una **invitación por correo** con un enlace (vale 3 días) para que la persona cree su propia contraseña; el dueño nunca la conoce. Si el correo falla, usa **Reenviar invitación** en la lista de usuarios. En su primer ingreso la persona configura su doble factor con su celular y guarda sus códigos de recuperación. Quien olvide su contraseña usa «¿Olvidaste tu contraseña?» en el ingreso (requiere el correo SMTP configurado; ver `docs/correo_smtp.md`).

| Rol | Qué puede hacer | Qué NO puede |
|---|---|---|
| **Dueño / administrador** | Todo: cargas, hallazgos, fiscal, configuración, usuarios, cierre de periodos, auditoría | — |
| **Contador o revisor** | Ver todo, gestionar hallazgos, simulador, exportar informes | Cargar archivos, cambiar configuración |
| **Asistente de carga** | Subir archivos (balance, auxiliares, facturas DIAN, retenciones, extracto), ver la vista previa y confirmar la importación, ver hallazgos, terceros y facturas | Ver IVA/retención/renta/ICA/exógena, proyecciones, informes, configuración, usuarios, auditoría; cerrar periodos |
| **Consulta** | Ver tablero, hallazgos, terceros, facturas, calendario | Cargar, exportar, ver lo fiscal |
| **Contratista** (Ideako) | Ver su pantalla: entregas, informes y observaciones | Todo lo demás |

Todo lo que hace cada usuario (ingresos, cargas, confirmaciones, descargas, cambios) queda en **Auditoría** con su nombre y hora.

## Persona que carga "todos los comprobantes"
El sistema **no registra comprobantes uno por uno** (eso sigue en World Office). Lo que se carga cada mes son los **archivos exportados**, que contienen todos los comprobantes del periodo:

1. **Balance de prueba** del mes (World Office).
2. **Auxiliares** del mes (World Office): trae todos los comprobantes con documento, tercero y valores.
3. **Facturas electrónicas** emitidas y recibidas del mes (Excel de la DIAN, o XML/zip).
4. **Retenciones practicadas** del mes y, si aplica, el **extracto bancario**.

Pasos de la persona (rol *Asistente de carga*): **Cargas → Nueva carga** → elegir tipo, año y mes → subir → revisar la vista previa → si las columnas no coinciden, "Ajustar mapeo" (se hace una sola vez por tipo de archivo y queda guardado) → **Confirmar importación**. Después de cada importación el sistema recalcula los controles y el dueño o el contador revisan los **Hallazgos**.

Buenas prácticas:
- Un periodo se cierra desde Configuración (solo el dueño) cuando está revisado; un periodo cerrado no admite más cargas.
- Si se sube el mismo archivo dos veces el sistema lo avisa (misma huella); si se sube uno corregido, el nuevo queda como vigente y el anterior se conserva.
- Esta persona verá nombres y NIT de terceros, facturas y valores del mes. Hay que contar con su autorización para el tratamiento de datos (Ley 1581 de 2012) y darle solo este rol.
