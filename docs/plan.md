# Plan de implementación — Sistema contable DH TRANS-STORAGE SAS

Oct 9, 2026 · @Daniel Henao

## Resumen y alcance

Se construirá una aplicación web propia (Django + PostgreSQL) que actúe
como segunda verificación independiente de la contabilidad de DH
TRANS-STORAGE SAS: recibe los exportes de World Office y de la DIAN,
detecta errores, concilia impuestos contra lo declarado y avisa los
vencimientos. No reemplaza a World Office ni firma declaraciones.

- **Entra:** balance de prueba y auxiliares (Excel/CSV de World Office),
  facturas electrónicas (Excel/XML de la DIAN), borradores y
  declaraciones que entregue el contratista.

- **Sale:** alertas de error, conciliaciones de IVA y retención,
  borradores propios de liquidación para contrastar, calendario con
  avisos, informes mensuales y proyecciones.

- **No hace:** causar ni facturar (sigue en World Office), presentar
  declaraciones ante la DIAN (lo hace Ideako, con la firma del
  profesional que corresponda) ni dar asesoría tributaria definitiva.

- **Contexto:** World Office corre en servidor propio y sin API, así que
  la carga es por archivos. El contrato CT-0029-2026 con Ideako
  (8-oct-2026 a 8-oct-2027, \$500.000 + IVA mensuales) cubre revisión
  mensual y presentación de impuestos, pero no registro ni causación. El
  sistema es el control del lado de la empresa.

## Obligaciones según el RUT

El RUT (actualización del 15-abr-2025, generado el 17-jul-2026) registra
nueve responsabilidades que el sistema debe cubrir, más una obligación
distrital (ICA) que no aparece en el RUT.

| Código RUT | Responsabilidad                            | Qué exige al sistema                                                                                                                   |
|------------|--------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| 05         | Renta y complementarios, régimen ordinario | Declaración anual con dos cuotas, anticipo y conciliación fiscal vs contable                                                           |
| 07         | Retención en la fuente a título de renta   | Declaración y pago mensual; control de base, tarifa y tercero por pago                                                                 |
| 09         | Retención en la fuente en el IVA           | Control de ReteIVA; verificar con el contador en qué formulario se declara                                                             |
| 10         | Obligado aduanero                          | Control de operaciones de comercio exterior, si las hay (el RUT también lista un usuario aduanero código 23: verificar su significado) |
| 14         | Informante de exógena                      | Reporte anual; validar terceros, valores y topes durante el año, no al final                                                           |
| 42         | Obligado a llevar contabilidad             | Libros, soportes y cierre bajo NIIF                                                                                                    |
| 48         | Impuesto sobre las ventas (IVA)            | Declaración cuatrimestral (confirmado por la empresa); conciliar FE vs contabilidad vs declarado                                       |
| 52         | Facturador electrónico                     | Control de numeración, notas crédito y documento soporte                                                                               |
| 55         | Informante de beneficiarios finales        | Registro y actualización del RUB (ver calendario)                                                                                      |

**Datos de la empresa en el RUT:** persona jurídica con matrícula
mercantil desde 2015, vigilada por la Superintendencia de Sociedades,
capital 100% nacional privado y domicilio en Bogotá (Impuestos de
Bogotá). Actividad principal CIIU 4651, secundaria 4923 y otras 5320 y
9511 (verificar las descripciones exactas en la DIAN: determinan la
tarifa de ICA y las retenciones).

**Responsables:** representante legal principal Candy Yesenia Henao
Molina (desde 12-jun-2017); revisor fiscal principal María Bernarda
Lloreda Chica (desde 20-oct-2022); contador Daniel Orlando Henao Molina
(desde 1-feb-2025).

**Punto a aclarar:** el contrato con Ideako no dice quién firma cada
declaración. El sistema debe registrar para cada obligación quién la
elabora, quién la revisa y quién la firma (contador o revisor fiscal), y
el RUT debe actualizarse si el contador cambia.

## Calendario tributario verificado (NIT 900.902.549, terminado en 9)

Hay fechas confirmadas hasta enero de 2027, y una exige acción: la
retención de septiembre vence el 22-oct-2026 y está pendiente de
presentar. El ICA de Bogotá del 4.º bimestre vencía hoy 9-oct-2026 y la
empresa ya lo declaró y pagó. Los plazos nacionales salen del [Decreto
2229 de
2023](https://normograma.dian.gov.co/dian/compilacion/docs/decreto_2229_2023.htm),
cuyos considerandos los mantienen vigentes desde 2024 "y siguientes";
para el dígito 9 casi todos caen en el 15.º día hábil del mes.

| Fecha límite                                 | Obligación                                        | Período         | Estado de la verificación                                                                                                                                                                                                                                     |
|----------------------------------------------|---------------------------------------------------|-----------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 9-oct-2026                                   | ICA Bogotá, 4.º bimestre                          | jul-ago 2026    | Una fuente secundaria ([INCP](https://incp.org.co/agendatributariaincp/noticias/2025/12/calendario-de-impuestos-distritales-2026/), Resolución SDH-000195 de 2025). Declarado y pagado, según la empresa                                                      |
| 22-oct-2026                                  | Retención en la fuente                            | sep 2026        | Dos fuentes ([VenciApp](https://venciapp.co/calendario-tributario-2026), [Actualícese](https://cdn.actualicese.com/herramientas/calendario-tributario-2026.pdf)) y cálculo del día hábil coinciden. Pendiente de presentar; incluida en el servicio de Ideako |
| 24-nov-2026                                  | Retención en la fuente                            | oct 2026        | Igual que la anterior                                                                                                                                                                                                                                         |
| 11-dic-2026                                  | ICA Bogotá, 5.º bimestre                          | sep-oct 2026    | Una fuente secundaria                                                                                                                                                                                                                                         |
| 22-dic-2026                                  | Retención en la fuente                            | nov 2026        | Dos fuentes y cálculo del día hábil coinciden                                                                                                                                                                                                                 |
| 25-ene-2027                                  | Retención en la fuente                            | dic 2026        | Dos fuentes coinciden                                                                                                                                                                                                                                         |
| 25-ene-2027                                  | IVA cuatrimestre 3 (sep-dic)                      | sep-dic 2026    | Dos fuentes coinciden                                                                                                                                                                                                                                         |
| 12-feb-2027                                  | ICA Bogotá, 6.º bimestre                          | nov-dic 2026    | Una fuente secundaria                                                                                                                                                                                                                                         |
| 26-feb-2027                                  | ICA Bogotá, declaración anual                     | año 2026        | Una fuente secundaria                                                                                                                                                                                                                                         |
| 31-mar-2027                                  | Renovación de matrícula mercantil                 | año 2027        | Plazo legal general; confirmar con la Cámara de Comercio                                                                                                                                                                                                      |
| 15.º día hábil de mayo 2027 (≈ 24-may-2027)  | Renta personas jurídicas: declaración y 1.ª cuota | AG 2026         | Estimada: el decreto fija la regla, no una lista 2027                                                                                                                                                                                                         |
| 15.º día hábil de julio 2027 (≈ 23-jul-2027) | Renta personas jurídicas: 2.ª cuota               | AG 2026         | Estimada, igual                                                                                                                                                                                                                                               |
| Sin publicar                                 | Exógena                                           | AG 2026         | No verificada: la DIAN suele fijar las fechas por resolución a fin de año                                                                                                                                                                                     |
| Sin verificar                                | Beneficiarios finales (RUB)                       | actualizaciones | No verificada: las fuentes consultadas no son oficiales ni coinciden; pedir fecha y norma a Ideako                                                                                                                                                            |

**Qué cambia el calendario para el diseño:** dos fuentes secundarias
discrepan en la 2.ª cuota de renta de 2026 (22 vs 23 de julio). El
cálculo con festivos da el 22. Por eso el sistema no debe copiar fechas:
debe calcularlas con la regla (día hábil n según el último dígito del
NIT) y una tabla de festivos, y compararlas cada diciembre contra el
calendario oficial de la DIAN.

**Periodicidad del IVA:** es cuatrimestral (confirmado por la empresa);
pasaría a bimestral si los ingresos brutos del año anterior fueran de
92.000 UVT o más (unos \$4.581 millones con la UVT 2025 de \$49.799). El
sistema guarda la periodicidad como parámetro con vigencia y alerta
cuando los ingresos del año se acerquen a ese tope.

**Pendientes con Ideako, por escrito:** el contrato excluye obligaciones
incumplidas antes del servicio (8-oct-2026). La empresa confirmó que el
ICA del 4.º bimestre ya está declarado y pagado, y que la retención de
septiembre (22-oct-2026) está incluida en el servicio; conviene dejar
esa inclusión por escrito.

**Fechas laborales que el sistema también debe avisar** (norma laboral,
no tributaria; nómina y seguridad social las lleva la empresa según el
contrato): intereses de cesantías hasta el 31 de enero, consignación de
cesantías hasta el 14 de febrero y primas el 30 de junio y el 20 de
diciembre. Verificar con el responsable de nómina.

**Fuentes consultadas:** [Decreto 2229 de 2023 (normograma
DIAN)](https://normograma.dian.gov.co/dian/compilacion/docs/decreto_2229_2023.htm),
[Calendario 2026 de
Actualícese](https://cdn.actualicese.com/herramientas/calendario-tributario-2026.pdf),
[VenciApp](https://venciapp.co/calendario-tributario-2026),
[Gerencie](https://www.gerencie.com/calendario-dian), [INCP, impuestos
distritales
2026](https://incp.org.co/agendatributariaincp/noticias/2025/12/calendario-de-impuestos-distritales-2026/)
y [INCP, exógena AG
2025](https://incp.org.co/publicaciones/infoincp-publicaciones/impuestos/2026/07/dian-ajusto-formatos-y-amplio-plazos-para-informacion-exogena-del-ano-gravable-2025/).
Consulta del 9-oct-2026; la DIAN prevalece ante cualquier diferencia.

## Arquitectura técnica

La arquitectura es un monolito Django en un solo VPS: más simple de
operar, asegurar y respaldar que servicios separados, y suficiente para
una sola empresa.

<img src="img/media/image1.png" style="width:6in;height:3.46428in"
alt="arquitectura · un VPS con Docker Compose" />

arquitectura · un VPS con Docker Compose

Las flechas de la izquierda son archivos que se suben por la web; las de
la derecha, pantallas e informes. La IA recibe solo hallazgos ya
calculados, con los datos mínimos y sin identificadores innecesarios.

**Pila tecnológica:** Python y Django, PostgreSQL, Celery con Redis,
HTMX y Tailwind en el frontend, pandas para leer y cruzar los Excel,
lxml para los XML de facturas, WeasyPrint u openpyxl para los informes,
django-otp para el doble factor y pruebas automáticas con pytest. Cada
regla tributaria lleva pruebas con casos reales anonimizados.

**Estructura del repositorio:** un directorio por app de Django, docker/
con el despliegue, docs/ con cada regla y su fuente normativa, y un
archivo CLAUDE.md con las convenciones para Claude Code.

## Módulos del ciclo contable y modelo de datos

El sistema cubre el ciclo contable completo como control sobre World
Office: no registra ni causa, pero verifica cada etapa y deja evidencia.
Cada módulo es una app de Django independiente.

| Etapa del ciclo                | Qué hace el sistema                                                                       | Qué sigue en World Office    |
|--------------------------------|-------------------------------------------------------------------------------------------|------------------------------|
| Registro y causación           | Verifica asientos, soportes, duplicados y causaciones pendientes contra las facturas DIAN | Registrar y causar           |
| Terceros                       | Valida NIT/DV, duplicados y datos mínimos para exógena                                    | Maestro de terceros          |
| Conciliaciones                 | Bancos, cartera, proveedores, IVA y retención                                             | Contabilizar ajustes         |
| Activos fijos y cierre mensual | Revisa depreciación, provisiones y saldos de naturaleza contraria                         | Depreciar y cerrar           |
| Nómina y seguridad social      | Controla provisiones y fechas; la nómina la lleva la empresa según el contrato            | Liquidar nómina              |
| Impuestos                      | Borradores propios de IVA, retención, ICA y renta para contrastar con los del contratista | Nada                         |
| Información exógena            | Valida valores, topes y terceros durante el año                                           | Generar archivos, si aplica  |
| Estados financieros NIIF       | Indicadores, comparativos y notas de apoyo                                                | Emitir los estados oficiales |
| Calendario y cumplimiento      | Vencimientos, responsables, estado y alertas                                              | Nada                         |
| Contratista                    | Entregas mensuales, informe de Ideako dentro de 15 días y observaciones                   | Nada                         |

**Apps de Django:** empresa, terceros, contabilidad, facturacion,
impuestos, calendario, conciliaciones, controles, analitica, reportes,
asistente y contratistas.

**Entidades principales:**

| Entidad                | Para qué sirve                                                                             |
|------------------------|--------------------------------------------------------------------------------------------|
| Periodo                | Año y mes con estado: abierto, en revisión, cerrado. Un periodo cerrado no se modifica     |
| ArchivoCargado         | Cada exporte con huella (hash), origen, usuario y fecha. Nunca se sobrescribe              |
| Tercero                | NIT, DV, razón social, tipo, régimen, declarante y autorretenedor                          |
| Cuenta y SaldoCuenta   | Plan de cuentas y saldos por periodo (inicial, débitos, créditos, final)                   |
| Factura                | Documento DIAN, valores, estado de causación y vínculo con el asiento                      |
| Retencion              | Pago, concepto, base, tarifa aplicada, retenido y teórico                                  |
| Declaracion            | Tipo, periodo, valores propios vs declarados, estado y quién la firmó                      |
| Obligacion             | Vencimiento calculado, responsable, estado y evidencia de presentación                     |
| Regla y Hallazgo       | Regla que se disparó, registro afectado, severidad y estado: abierto, explicado, corregido |
| Parametro con vigencia | UVT, tarifas, bases y festivos con fecha de inicio y fin, sin valores fijos en el código   |
| RegistroAuditoria      | Quién hizo qué y cuándo, incluida cualquier lectura de datos sensibles                     |

## Diseño del frontend

El frontend se sirve desde el mismo Django (plantillas + HTMX + Tailwind
CSS + Chart.js): sin aplicación separada que mantener, rápido en el
celular y con el mismo login para todo. Se descarta React aparte para el
MVP; si más adelante hace falta, la API ya queda disponible.

**Principios de diseño:** una sola pregunta por pantalla (¿qué está mal
este mes?), semáforo verde/ámbar/rojo con el mismo significado en todo
el sistema, tablas con filtros y exportación a Excel, y diseño que
funcione primero en el celular, porque es donde el dueño consultará.

| Pantalla             | Contenido                                                                                                          | Usuario principal |
|----------------------|--------------------------------------------------------------------------------------------------------------------|-------------------|
| Tablero del mes      | Selector de año y mes, semáforo general, 10 indicadores clave, próximos vencimientos y gráficos de IVA y retención | Dueño             |
| Cargas               | Subir balance, auxiliares, facturas DIAN y declaraciones; previsualizar, validar columnas y confirmar              | Dueño y asistente |
| Hallazgos            | Bandeja de errores y diferencias con severidad, filtros y estados; cada uno con explicación y evidencia            | Dueño y contador  |
| Terceros             | Maestro con validación de NIT/DV y datos faltantes para exógena                                                    | Asistente         |
| Facturas             | Cruce DIAN vs contabilidad por mes con alertas                                                                     | Asistente         |
| IVA y retención      | Conciliación mensual y por periodo: propio vs contabilidad vs declarado                                            | Dueño y contador  |
| Renta, ICA y exógena | Borradores y conciliación fiscal vs contable; validaciones anticipadas                                             | Contador          |
| Calendario           | Vista de mes y lista, con responsable, estado y evidencia de presentación                                          | Todos             |
| Informes             | Informe mensual en PDF y Excel, estados financieros e indicadores                                                  | Dueño             |
| Contratista          | Entregas a Ideako, sus informes y observaciones pendientes                                                         | Dueño             |
| Configuración        | Parámetros con vigencia, usuarios, roles y copias de seguridad                                                     | Administrador     |

**Estilo visual:** sobrio y profesional (azul marino y gris, un solo
color de acento), tipografía legible, tarjetas de indicadores arriba y
detalle abajo. En el tablero cada indicador abre su detalle en un clic y
cada hallazgo muestra de dónde sale cada cifra.

## Motor de reglas, liquidación de impuestos y predicción

Las cifras las calculan reglas deterministas, no la IA: así cada
resultado se puede explicar y repetir. La IA solo redacta explicaciones
y preguntas para el contador a partir de los hallazgos.

**Detección de errores (catálogo inicial):**

| Grupo      | Reglas                                                                                                              |
|------------|---------------------------------------------------------------------------------------------------------------------|
| Integridad | Débitos ≠ créditos; saldo calculado ≠ saldo reportado; cuentas con saldo de naturaleza contraria; periodo sin carga |
| Terceros   | DV errado, NIT duplicado, datos incompletos, tercero en facturas que no está en el maestro                          |
| Facturas   | Factura DIAN sin causar, causada con valor distinto, duplicada, notas crédito sin vínculo, fecha fuera del periodo  |
| IVA        | IVA FE vs cuenta 2408; IVA descontable sin soporte; saldo declarado vs propio; periodicidad inconsistente           |
| Retención  | Base mínima en UVT, tarifa por concepto y condición del tercero, retenido vs teórico, declarado vs contabilidad     |
| Renta      | Diferencias contable-fiscal sin explicar, anticipo, tasa mínima de tributación, gastos no deducibles y soportes     |
| Exógena    | Terceros sin dato, valores por debajo del tope, diferencias contra auxiliares                                       |
| Calendario | Obligación sin responsable, sin evidencia de presentación o próxima a vencer                                        |

**Liquidación de impuestos:** el sistema calcula borradores propios de
IVA, retención, ICA y renta con parámetros que tienen fecha de vigencia
(UVT, tarifas, bases y topes). Los borradores sirven para contrastar con
los del contratista, nunca para presentar. Toda diferencia queda como
hallazgo con su explicación.

**Análisis y predicción, por niveles:**

1.  Indicadores del mes: liquidez, endeudamiento, rotación de cartera y
    proveedores, margen y gasto por rubro, comparados con el mismo mes
    del año anterior.

2.  Anomalías: valores atípicos por cuenta y tercero (rango
    intercuartílico y desviación robusta) y revisión de dígitos
    iniciales para detectar montos manipulados.

3.  Proyecciones: ingresos, IVA y retención por pagar y flujo de caja
    con modelos simples (promedios estacionales, suavizado exponencial),
    siempre con banda de incertidumbre.

4.  Estimación de renta, IVA, retención e ICA del año con datos
    acumulados y escenarios, para provisionar caja y decidir antes del
    cierre (ver la sección siguiente).

Las proyecciones son estimaciones de gestión y no se usan como cifras
para declarar. Cada una muestra el método, los datos que usó y su margen
de error.

## Proyección de impuestos y simulador de cierre

Cada vez que subes un informe mensual, el sistema recalcula cuánto
pagarías de cada impuesto al cierre del año y muestra qué decisiones aún
están a tiempo antes del 31 de diciembre. Es una estimación de gestión:
no se usa para declarar.

| Impuesto               | Qué muestra                                                                                        | Con qué datos                                                                                 | Se recalcula             |
|------------------------|----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|--------------------------|
| Renta                  | Impuesto estimado del año, anticipo, tasa efectiva y verificación de la tasa mínima de tributación | Acumulado contable, diferencias contable-fiscal conocidas y proyección de los meses restantes | Cada informe mensual     |
| IVA                    | Saldo por pagar o a favor del cuatrimestre en curso                                                | IVA generado y descontable de las facturas DIAN del periodo                                   | Cada carga de facturas   |
| Retención en la fuente | Valor a pagar del mes en curso y comparación con meses anteriores                                  | Pagos con su base, tarifa y tercero                                                           | Cada carga de auxiliares |
| ICA                    | Valor estimado del bimestre en curso y del año                                                     | Ingresos por actividad y tarifa vigente en Bogotá                                             | Cada informe mensual     |
| Caja de impuestos      | Calendario de pagos de los próximos 12 meses con montos estimados frente a la caja proyectada      | Las cuatro estimaciones y el calendario por regla                                             | Cada recálculo           |

**Cómo se calcula:**

1.  Se toma lo real: el acumulado hasta el último mes cerrado.

2.  Se proyectan los meses restantes con modelos simples (promedio
    estacional, suavizado exponencial) y se arman tres escenarios: base,
    favorable y adverso, cada uno con su rango.

3.  Se aplican las mismas reglas deterministas de los borradores, con
    los parámetros vigentes (UVT, tarifas, topes). La IA no calcula.

4.  Cada cifra muestra sus supuestos, el método y los datos que usó.

**Simulador de cierre ("qué pasa si"):** antes de fin de año puedes
mover variables y ver el efecto en el impuesto y en la caja: ingresos
que se facturarían antes o después del cierre, gastos o compras de
activos planeados, cartera que se castigaría o provisionaría y pagos
pendientes de causar. Cada simulación se guarda con autor y fecha y se
marca como estimación. Las decisiones con efecto tributario se revisan
con el contador antes de ejecutarlas.

**Alertas:** aviso cuando el impuesto estimado supera la caja proyectada
para su fecha de pago, cuando hay saldo a favor de IVA, cuando la tasa
efectiva se acerca al mínimo o cuando el estimado cambia más de un
umbral (parámetro) entre dos meses.

**Límites:** la estimación de renta depende de que la conciliación
fiscal esté al día. Si faltan diferencias por registrar, el sistema lo
advierte en la misma pantalla y amplía el rango.

**Entrega por fases:** versión inicial en la F2, para tenerla antes del
cierre del año (renta acumulada con el balance real, IVA y retención,
con un escenario), ajuste en la F4 con la conciliación fiscal y el ICA,
y versión completa en la F5 (escenarios, simulador, alertas y
comparativo con años anteriores).

## Seguridad, habeas data y copias de seguridad

El sistema guardará información tributaria y datos personales de
empleados y terceros, así que la seguridad es requisito del MVP, no una
fase posterior.

- **Acceso:** login con doble factor, roles (administrador, contador o
  revisor en solo lectura, asistente de carga, contratista con acceso
  limitado) y cierre automático de sesión.

- **Red:** HTTPS obligatorio, firewall que solo abre los puertos 22
  (solo con llave), 80 y 443, y bloqueo de intentos repetidos de
  ingreso.

- **Datos:** base de datos sin acceso desde internet, secretos en
  variables de entorno fuera del repositorio, y mínimo de datos
  personales: no se cargan datos de nómina si el control no los
  necesita.

- **Trazabilidad:** registro de auditoría de cargas, cambios, descargas
  y cierres; los archivos cargados se conservan con su huella y no se
  sobrescriben.

- **Copias de seguridad:** copia diaria cifrada de la base de datos y de
  los archivos, enviada fuera del servidor, más las copias del propio
  proveedor. Se prueba una restauración completa cada mes. Regla 3-2-1:
  tres copias, dos medios, una fuera del servidor.

- **Habeas data:** el tratamiento de datos personales se rige por la Ley
  1581 de 2012 y el Decreto 1377 de 2013, que el propio contrato con
  Ideako cita. La empresa debe tener política de tratamiento y
  autorizaciones; el contador debe revisar el alcance.

- **Credenciales:** nunca se comparten por chat ni por correo. El
  despliegue usa una llave de acceso que la empresa puede revocar.

## Hosting en Hostinger VPS y despliegue

El sistema corre en un VPS de Hostinger, no en hosting compartido,
porque necesita base de datos, tareas programadas y acceso root. Antes
de comprar, confirma en el plan elegido que incluye acceso root/SSH y
copias de seguridad; no verifiqué precios ni planes actuales.

**Montaje del servidor (Docker Compose):** Django con gunicorn,
PostgreSQL, Redis con Celery para tareas programadas (alertas,
importaciones, informes) y un servidor web (Caddy) que entrega HTTPS
automático. Todo versionado en un repositorio privado de GitHub.

**Tamaño inicial (estimación a validar):** 2 vCPU y 4 GB de RAM alcanzan
para una sola empresa; se amplía si el uso lo pide.

**Pasos que haces tú, una sola vez:**

1.  Contratar el VPS con Ubuntu LTS y acceso por llave SSH.

2.  Registrar un dominio o subdominio y apuntarlo al VPS (registro DNS
    tipo A).

3.  Crear un repositorio privado en GitHub y una llave de despliegue de
    solo lectura para el servidor.

4.  Crear una cuenta de almacenamiento externo (compatible con S3) para
    las copias de seguridad cifradas.

**Pasos que prepara Claude Code:** archivos Docker, script de arranque
seguro del servidor, configuración de copias de seguridad, comandos de
actualización (git pull y docker compose up -d) y una lista de
verificación para cada despliegue.

**Ambientes:** desarrollo en tu computador con datos de prueba;
producción en el VPS. No se usan datos reales en desarrollo.

## Plan por fases y arranque con Claude Code

El MVP (fases 0 a 3) queda en uso hacia la semana 9, y cada fase termina
en una puerta que exige datos reales, no solo código que corre. Los
tiempos son estimaciones y dependen de qué tan rápido lleguen los
exportes y las aclaraciones del contador.

<img src="img/media/image2.png" style="width:6in;height:3.25in"
alt="plan por fases · 6 fases, 5 puertas de calidad" />

plan por fases · 6 fases, 5 puertas de calidad

**Puertas de calidad:**

- **P0:** el sistema responde por HTTPS con doble factor y se restaura
  una copia de seguridad completa.

- **P1:** el balance de un mes real se importa sin errores y sus totales
  cuadran con World Office.

- **P2:** el IVA y la retención de un mes real coinciden con lo
  declarado, o cada diferencia queda explicada. La proyección inicial de
  renta se calcula con el balance real.

- **P3:** el primer informe mensual se comparte con Ideako y el
  calendario muestra las fechas verificadas.

- **P4:** los borradores de renta, ICA y exógena y la proyección de
  impuestos de un cierre de prueba se contrastaron con el contador, y
  cada supuesto quedó documentado.

| Fase                                     | Entregables                                                                                                                                                              | Termina en               |
|------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------|
| F0 Base y despliegue                     | Repositorio, Docker Compose, Django con login y doble factor, HTTPS, copias cifradas e integración continua                                                              | P0                       |
| F1 Cargas y control básico               | Importadores de balance y auxiliares, terceros con DV, validaciones de integridad y tablero inicial                                                                      | P1                       |
| F2 Facturas, IVA, retención y calendario | Importador DIAN, cruces, conciliación de IVA y retención, calendario por regla con festivos y alertas por correo, y proyección inicial de renta, IVA y retención del año | P2                       |
| F3 Hallazgos, informes y contratista     | Bandeja de hallazgos con estados, informe mensual en PDF y Excel, módulo del contratista                                                                                 | P3                       |
| F4 Renta, ICA y exógena                  | Borradores y conciliación fiscal, validación anticipada de exógena, calendario anual, y ajuste de la proyección con la conciliación fiscal y el ICA                      | P4                       |
| F5 Analítica, predicción e IA            | Indicadores, anomalías, proyecciones con margen de error, escenarios y simulador de cierre, y asistente que explica hallazgos                                            | Revisión con el contador |

**Cómo se trabaja con Claude Code:** este documento se guarda como
docs/plan.md en el repositorio y el archivo CLAUDE.md fija las reglas
que Claude Code respeta en cada sesión. Cada fase se pide con un prompt
corto, se revisa la lista de archivos antes de escribir código y se
prueba con datos de ejemplo.

\# DH TRANS-STORAGE — Sistema de control contable  
  
\## Qué es  
Aplicación Django + PostgreSQL que verifica la contabilidad llevada en
World Office. No registra ni causa, y no presenta declaraciones.  
  
\## Datos confirmados de la empresa  
- DH TRANS-STORAGE SAS, NIT 900.902.549-7 (termina en 9), domicilio en
Bogotá.  
- Contabilidad en World Office instalado en servidor propio, sin API: la
entrada es por exportes Excel/CSV.  
- Contratista contable: Ideako (contrato CT-0029-2026). El sistema es
una segunda verificación independiente.  
- IVA cuatrimestral. ICA de Bogotá bimestral (inferido; confirmar): el
4.º bimestre de 2026 ya está declarado y pagado.  
- Retención en la fuente mensual: la de septiembre vence el 22-oct-2026,
está pendiente de presentar y está incluida en el servicio de Ideako.  
- UVT 2026 = \$52.374. Va como parámetro con vigencia, nunca fija en el
código.  
  
\## Reglas obligatorias  
- Los cálculos tributarios son deterministas y viven en
\`impuestos/reglas/\`. La IA nunca calcula.  
- Ningún parámetro tributario (UVT, tarifas, bases, fechas, festivos,
periodicidad) va fijo en el código: se guarda en tablas con fecha de
vigencia.  
- Cada regla cita su norma en \`docs/reglas/\` y tiene pruebas con casos
anonimizados.  
- Los archivos cargados no se sobrescriben: se guardan con huella
(hash).  
- Todo cambio de datos escribe en RegistroAuditoria.  
- Nunca hay datos reales ni secretos en el repositorio.  
- Si falta un dato o una norma, se pregunta o se marca como pendiente;
nunca se inventa.  
- La interfaz va en español colombiano.  
  
\## Definición de terminado  
Pruebas pasando, regla documentada con su fuente, migraciones, auditoría
y revisión básica de seguridad.

**Primer prompt (Fase 0):**

Lee CLAUDE.md y docs/plan.md completos. Construye de forma autónoma y en
orden el sistema de las fases F0 a F5, sin esperar mi aprobación entre
fases. No voy a estar disponible mientras trabajas: toma las decisiones
razonables, anótalas en docs/decisiones.md y sigue.  
  
Contexto confirmado (prevalece sobre lo que diga el plan si hay
diferencias):  
- La contabilidad está en World Office instalado en servidor propio, sin
API. Todo ingresa por exportes Excel/CSV y por facturas electrónicas de
la DIAN.  
- IVA cuatrimestral. ICA de Bogotá bimestral (el 4.º bimestre de 2026 ya
está declarado y pagado). Retención en la fuente mensual; la de
septiembre vence el 22-oct-2026 y está incluida en el servicio de
Ideako.  
- El sistema verifica; no registra, no causa ni presenta
declaraciones.  
  
Modo de trabajo:  
1. Crea desde el inicio docs/PROGRESO.md con las fases y tareas.
Actualízalo y haz un commit al terminar cada tarea, para poder retomar
si la sesión se corta.  
2. Usa solo datos sintéticos que imiten los exportes de World Office
(balance de prueba, auxiliares) y de la DIAN (facturas). Como no conoces
los formatos reales, los importadores trabajan con perfiles de mapeo de
columnas configurables desde la interfaz, para adaptarlos a mis archivos
reales sin tocar código.  
3. Ningún parámetro tributario va fijo en el código (UVT, tarifas,
bases, fechas, festivos, periodicidad): todo en tablas con vigencia. El
único valor confirmado es UVT 2026 = \$52.374. Los demás se cargan como
"por verificar" o quedan vacíos con un aviso visible en pantalla. No
inventes tarifas ni normas.  
4. pytest y ruff pasan en cada paso. No avances con pruebas en rojo.  
5. Prioridad si el tiempo se acaba: F0, F1, F2 (con la proyección
inicial de renta, IVA y retención), F3, F4 y F5.  
6. Solo detente y pregúntame ante: credenciales o acceso al VPS, algo
irreversible o una decisión que cambie el alcance.  
7. No uses datos reales ni secretos en el repositorio. Las credenciales
van en variables de entorno.  
  
Entregables clave:  
- F0: proyecto Django (Python 3.12), PostgreSQL, Redis, Celery, Docker
Compose con Caddy (HTTPS automático), login con doble factor
(django-otp), roles (dueño, contador, consulta), RegistroAuditoria,
GitHub Actions con pytest y ruff, y deploy/bootstrap.sh para un VPS
Ubuntu LTS (usuario sin root, firewall, fail2ban, Docker, copias
cifradas diarias con copia fuera del servidor).  
- F1 a F5: lo que define docs/plan.md, incluida la sección de proyección
de impuestos y simulador de cierre.  
  
Al terminar, entrega: README para correrlo en local, docs/despliegue.md
paso a paso para que yo lo despliegue en el VPS de Hostinger, y una
lista de lo que falta validar con mis datos reales y con el contador.

## Riesgos y puntos que debe validar el contador

El mayor riesgo es tratar las salidas del sistema como definitivas: es
un control y un apoyo, y la firma sigue siendo del profesional
responsable.

| Riesgo                                                  | Mitigación                                                                                               |
|---------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Cambian las normas, tarifas o fechas                    | Parámetros con vigencia, calendario calculado por regla y revisión cada diciembre contra la DIAN         |
| Los exportes de World Office traen formatos inesperados | Probar con datos reales en la Fase 1 y guardar un perfil de importación por tipo de reporte              |
| La IA se equivoca o inventa                             | La IA no calcula ni decide; solo explica hallazgos ya calculados y cita la regla y los datos             |
| Fuga de datos                                           | Doble factor, roles, auditoría, copias cifradas y datos mínimos                                          |
| El alcance crece sin control                            | MVP limitado a carga, cruces, alertas y calendario; el resto entra por fases con criterios de aceptación |
| Dependencia de una sola persona o proveedor             | Código en repositorio propio, documentación y despliegue reproducible                                    |
| Se confunde control con presentación                    | Cada declaración registra quién la elabora, revisa y firma                                               |

**Puntos que debe confirmar el contador o el revisor fiscal antes de la
Fase 2:**

1.  Periodicidad del IVA: confirmada como cuatrimestral; revisar cada
    año contra el tope de 92.000 UVT de ingresos brutos.

2.  Tarifa del ICA en Bogotá según la actividad y el RIT, y periodicidad
    bimestral (se infiere del 4.º bimestre ya declarado).

3.  Tarifas y bases de retención aplicables a las compras y servicios
    reales de la empresa.

4.  En qué formulario se declara la retención de IVA (código 09 del
    RUT).

5.  Quién firma cada declaración y si el RUT necesita actualización.

6.  Dejar por escrito que la retención de septiembre (22-oct-2026) está
    dentro del servicio de Ideako; el ICA del 4.º bimestre ya está
    declarado y pagado.

7.  Fecha y norma vigente de actualización del registro de beneficiarios
    finales.

8.  Significado del usuario aduanero código 23 en el RUT y si hay
    operaciones de comercio exterior.
