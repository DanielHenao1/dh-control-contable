# Guía de pruebas: cómo funciona cada parte

Sirve para probar el sistema con **datos sintéticos** antes de cargar información real. Todo esto se hace en https://contabilidad.dhstore.com.co con el usuario dueño. Los archivos de ejemplo están en `docs/ejemplos/` (ver su README).

> Antes del primer dato **real**: la copia de seguridad fuera del servidor debe estar activa (`docs/respaldo_en_mi_pc.md`). Hoy está pendiente.

## Cómo está organizado (idea general)
El sistema **no registra ni causa**: verifica lo que se hizo en World Office. Recibe exportes (Excel/CSV/XML), los compara entre sí y con la DIAN, y avisa las diferencias como **hallazgos**. Los cálculos son reglas fijas (no IA). La IA solo redacta explicaciones y responde preguntas con datos ya calculados.

Roles: **dueño** (todo), **contador** (lectura y gestión de hallazgos, sin cargar ni configurar), **asistente de carga** (solo sube archivos), **consulta** (solo lectura), **contratista** (solo su panel). Detalle en `docs/usuarios_y_roles.md`.

## 1. Ingreso y seguridad
1. Entra con usuario y contraseña. Después pide el código de la aplicación de autenticación (doble factor). Tras 5 intentos fallidos se bloquea unos minutos.
2. «¿Olvidaste tu contraseña?» envía un enlace al correo del usuario (3 días, un solo uso). El doble factor no se salta.
3. La sesión se cierra sola a los 30 minutos sin actividad.

## 2. Usuarios (Configuración → Nuevo usuario)
1. Crea «Asistente de carga»: usuario, nombre, **correo** y rol *Asistente de carga*.
2. Debe llegar el correo de invitación (verde, con el logo). La persona crea su contraseña y configura su doble factor.
3. Si el correo falla: botón **Reenviar invitación** en la lista de usuarios. Todo queda en Auditoría.

## 3. Configuración antes de cargar
- **Parámetros** (Configuración): valores tributarios con fecha de vigencia (UVT, tarifas, cuentas contables). Estado *Por verificar* = el sistema avisa que ese cálculo depende de un dato sin confirmar. **No se confirma sin que Ideako lo valide.**
- Para las pruebas con los ejemplos, deja *Verificado* estos dos: `PUC_IVA_GENERADO = 240801` y `PUC_IVA_DESCONTABLE = 240802`. Con datos reales van las cuentas del plan de World Office.
- **Conceptos de retención** (Renta, ICA, exógena → Conceptos): crea `compras`, base mínima 27 UVT, tarifa 2,5 % (declarante), *Verificado*, vigente desde 1-ene-2026. Es solo para la prueba; las tarifas reales las confirma el contador.
- **Periodos**: abierto → en revisión → cerrado. Un periodo cerrado no admite cargas.
- Las fechas laborales (cesantías y primas) se dejan en el calendario como pendientes, aunque hoy no haya contratos: siguen alertando hasta que se marquen cumplidas.
- `ALERTA_PANTALLA_DIAS`: días de anticipación de la alerta en pantalla (hoy 30).

## 4. Cargas (menú Cargas → Nueva carga)
Tipos: balance de prueba, auxiliares, facturas DIAN (Excel o XML/zip), retenciones, extracto bancario, declaración (PDF) y otro soporte.

Qué pasa al subir un archivo:
1. **Revisión previa**: formato, que sea del tipo elegido, de la empresa y del periodo (ver `docs/validacion_de_cargas.md`). Si hay un error no se guarda y se explica; solo el dueño puede forzar con «Subir de todas formas» (queda auditado).
2. Se guarda con su **huella SHA-256** y **nunca se sobrescribe**; el mismo archivo dos veces te lleva al ya cargado.
3. **Vista previa** de las primeras filas. Si las columnas no se reconocen, **Ajustar mapeo** y queda un *perfil* reutilizable (pantalla Perfiles, a la que llegas desde el mapeo).
4. **Confirmar importación**. Solo ahí entran los datos y se ejecutan los controles.

Pruébalo así (Septiembre 2026, en este orden): balance → auxiliares → facturas recibidas → facturas emitidas → retenciones → extracto.
Pruebas de rechazo (deben **no** guardarse): sube `balance_2026-09.csv` como «Auxiliares»; `facturas_recibidas_2026-09.csv` marcando «Emitidas»; `extracto_banco_2026-09.csv` como «Balance».
Para una declaración: elige el formulario (**300 = IVA**, **350 = retención en la fuente**, 110 = renta); si el PDF es de otro formulario o de otro NIT, avisa.

## 5. Hallazgos (menú Hallazgos)
Tras confirmar los seis archivos de ejemplo deben quedar **abiertos** estos hallazgos:

| Regla | Qué debe decir | Por qué |
|---|---|---|
| FAC001 | Factura de compra FC1003 sin causar | Está en la DIAN, no en libros |
| FAC002 | Factura FC1004 causada por un valor distinto (119.000) | Libros 700.000 + IVA vs DIAN 800.000 + IVA |
| FAC006 | Salto en la numeración SE: falta la 503 | Ventas 501, 502 y 504 |
| IVA001 | IVA descontable DIAN 817.000 vs contabilidad 703.000 | Efecto de FC1003 y FC1004 |
| RET001 | Retención distinta de la teórica en FC-1002 | Retenido 40.000, teórico 50.000 |
| RET002 | Se retuvo bajo la base mínima en FC-1001 | Base 1.000.000 < 27 UVT |
| RET005 | Retención por pagos 65.000 vs contabilidad 92.500 | Falta una retención en el archivo |
| EXO001 / TER002 | Falta el tope de exógena; terceros sin dirección/ciudad | Datos maestros pendientes |

Cada hallazgo muestra *de dónde sale* (regla y norma), las cifras y la evidencia. Estados: **abierto → explicado → corregido** (se pone «explicado» con el motivo, «corregido» cuando se ajusta en World Office). **Volver a ejecutar los controles** recalcula. **Catálogo de reglas** lista todas las reglas y su fuente. «Redactar explicación con el asistente» usa un texto local mientras no haya clave de IA.

## 6. Tablero
Semáforo del mes (verde/ámbar/rojo según hallazgos), indicadores (ingresos, utilidad, margen, endeudamiento, liquidez, saldo de IVA, retención, próximo vencimiento) y gráficos de retención e IVA. Arriba, los bloques **vencidas** (rojo) y **próximas** (naranja). Los gráficos usan una librería externa: si no cargan, revisa la conexión del navegador.

## 7. Terceros y Facturas
- **Terceros**: maestro con NIT, dígito de verificación (se valida), datos para exógena y duplicados por razón social. Exporta a Excel.
- **Facturas**: DIAN vs contabilidad por documento (sin causar, valor distinto, duplicadas, notas crédito sin vínculo). Filtros y Excel.

## 8. IVA y retención, Conciliaciones, Renta/ICA/exógena
- **IVA y retención**: IVA del cuatrimestre (propio con facturas, contabilidad, declarado) y retención del mes (teórica, pagos, contabilidad, declarada). Con los ejemplos: generado 1.710.000 = 1.710.000; descontable 817.000 vs 703.000. Los «supuestos del cálculo» están al pie.
- **Conciliaciones**: auxiliares vs balance por grupo, cartera y proveedores por tercero, y **bancos**: escribe el prefijo de la cuenta del banco (`111005` en el ejemplo) para ver qué hay solo en el extracto (cargo bancario de 12.000) y qué solo en libros.
- **Renta, ICA, exógena**: renta estimada al corte, diferencias contable-fiscal, ICA Bogotá del bimestre, validación de exógena y registro de **declaraciones** del año (aquí se anota lo que presenta Ideako).

## 9. Proyección, simulador y análisis
- **Proyección**: impuesto estimado al cierre del año por escenario y caja de impuestos de 12 meses (se recalcula con los datos actuales).
- **Simulador** (dueño y contador): «qué pasa si» antes del cierre. Pide un nombre y cualquiera de estos supuestos: ingresos que se facturarían antes o después del cierre, gastos planeados, compra de activos, cartera a castigar o provisionar y pagos pendientes de causar. Calcula el efecto en el impuesto y guarda la simulación.
- **Análisis**: estados financieros por clase, valores atípicos por cuenta, terceros atípicos y primer dígito (Benford). Son alertas de revisión, no conclusiones.
Con un solo mes de datos las proyecciones son poco informativas: sirven para ver que funcionan.

## 10. Calendario
- Vista **Mes** (con selector de año y mes), **Lista** y **Reglas** (cómo se calcula cada fecha: día hábil n según el último dígito del NIT, fechas fijas de ICA, festivos).
- Colores: **rojo** vencida, **naranja** pendiente por vencer, **azul** presentada sin pago, **verde** cumplida. Las informativas (exógenas) quedan en verde al presentarse.
- Clic en una obligación: estado, responsables (elabora/revisa/firma), evidencia (acuse) y notas. Al marcarla presentada o pagada deja de alertar.
- Cada fecha trae su **verificación** (dos fuentes, una fuente, regla, no verificada): confirma las de una fuente con el calendario oficial.
- Se genera sola cada día; «Recalcular por regla» lo fuerza.

## 11. Informes y contratista
- **Informes**: informe mensual en PDF y Excel (indicadores, hallazgos abiertos, próximos vencimientos); registrar un informe como emitido.
- **Contratista** (Ideako): entregas mensuales, informes recibidos y observaciones del lado de la empresa, con respuesta del contratista.

## 12. Auditoría
Menú Auditoría (dueño): quién hizo qué y cuándo (cargas, importaciones, cierres, invitaciones, cambios de contraseña, preguntas a la IA). Solo se agrega, no se edita.

## 13. Correos
Todos son HTML con el logo y una etiqueta de color: INVITACIÓN, RECUPERAR CONTRASEÑA, ALERTA DE VENCIMIENTO (diaria, a 15/7/3/1 días y vencidas), RESUMEN SEMANAL (lunes 7:00) y PRUEBA. Pruebas desde el servidor:
```bash
docker compose exec web python manage.py probar_correo gerencia@dhtransstorage.com.co
docker compose exec web python manage.py enviar_resumen_semanal
```

## 14. Asistente de IA
Apagado hasta poner `ANTHROPIC_API_KEY`. Cuando se active: pantalla **Asistente**, solo dueño y contador; responde con el resumen minimizado del sistema, sin calcular. Ver `docs/asistente_ia.md`.

## Qué dejar para después de las pruebas
1. Confirmar con Ideako los **28 parámetros por verificar** (cuentas, tarifas, topes) y marcarlos *Verificados*.
2. Copia de seguridad fuera del servidor activa.
3. Subir los exportes **reales** de World Office y revisar si el perfil de columnas funciona o hay que mapearlo.
4. Encender la IA (clave de API con tope de gasto).
5. Borrar los datos de prueba del periodo antes de cargar los reales (pídemelo: no se borra desde la interfaz para proteger la trazabilidad).

## Límites conocidos
- No conocemos el formato real de los exportes de World Office ni de la DIAN: el reconocimiento de columnas puede requerir un perfil.
- Las fechas del calendario de ICA, ReteICA y exógenas salen de resúmenes de fuentes secundarias: verifícalas contra la norma antes de depender de ellas.
- Los hallazgos son una segunda revisión: no reemplazan al contador.
