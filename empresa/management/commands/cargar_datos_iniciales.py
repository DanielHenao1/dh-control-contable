"""Carga la empresa, los parámetros (marcados 'por verificar' salvo lo confirmado), reglas y contratista.

Es idempotente. Solo UVT 2026 y la periodicidad del IVA están confirmadas por la empresa; todo lo demás se
carga 'por verificar' o vacío para que el sistema lo muestre con aviso. No se inventan tarifas ni normas.
"""
from datetime import date

from django.core.management.base import BaseCommand

from calendario.dias_habiles import asegurar_festivos
from calendario.generador import generar_obligaciones
from calendario.models import Obligacion, ReglaVencimiento
from contratistas.models import Contratista
from empresa.models import Empresa, Parametro, PerfilImportacion
from empresa.vigencias import asegurar_vigencias
from terceros.nit import calcular_dv

V, PV = "verificado", "por_verificar"
PLAN = "Plan de implementación"

PARAMETROS = [
    # codigo, descripcion, tipo, valor, desde, hasta, estado, fuente
    ("UVT", "Unidad de Valor Tributario 2026", "decimal", "52374", date(2026, 1, 1), date(2026, 12, 31), V, "Confirmado por la empresa (plan de implementación)"),
    ("UVT", "Unidad de Valor Tributario 2025", "decimal", "49799", date(2025, 1, 1), date(2025, 12, 31), PV, "Citada en el plan; verificar contra la resolución DIAN"),
    ("IVA_PERIODICIDAD", "Periodicidad del IVA (cuatrimestral o bimestral)", "texto", "cuatrimestral", date(2025, 1, 1), None, V, "Confirmado por la empresa"),
    ("IVA_TOPE_BIMESTRAL_UVT", "Ingresos brutos del año anterior (UVT) desde los que el IVA es bimestral", "decimal", "92000", date(2025, 1, 1), None, PV, "Estatuto Tributario art. 600, según el plan; confirmar con el contador"),
    ("RENTA_TARIFA", "Tarifa general de renta personas jurídicas", "decimal", "0.35", date(2025, 1, 1), None, PV, "Estatuto Tributario art. 240; confirmar con el contador"),
    ("RENTA_TASA_MINIMA", "Tasa mínima de tributación (referencial)", "decimal", "0.15", date(2025, 1, 1), None, PV, "Estatuto Tributario art. 240 par. 6; confirmar con el contador"),
    ("RENTA_ANTICIPO_PORCENTAJE", "Porcentaje de anticipo de renta (referencial)", "decimal", "", date(2025, 1, 1), None, PV, "Definir con el contador según años de declaración"),
    ("ICA_ACTIVIDAD_PRINCIPAL", "CIIU de la actividad principal para ICA", "texto", "4651", date(2025, 1, 1), None, PV, "RUT: actividad principal 4651; verificar descripción exacta en la DIAN"),
    ("EXOGENA_TOPE_PESOS", "Tope por tercero para reportar en exógena (pesos)", "decimal", "", date(2025, 1, 1), None, PV, "Resolución DIAN de exógena del año gravable: cargar"),
    ("EXOGENA_TOPE_UVT", "Tope por tercero para exógena (en UVT), alternativo al de pesos", "decimal", "", date(2025, 1, 1), None, PV, "Resolución DIAN de exógena del año gravable: cargar"),
    ("EXOGENA_DIAN_UMBRAL_UVT", "Umbral en UVT de ingresos brutos desde el cual hay que reportar la exógena nacional (DIAN)", "decimal", "", date(2025, 1, 1), None, PV, "Resolución 000227 de 2025 de la DIAN y sus modificaciones: cargar el valor que corresponda a la empresa (las fuentes secundarias no coinciden)"),
    ("EXOGENA_DISTRITAL_UMBRAL_UVT", "Umbral en UVT de ingresos brutos desde el cual hay que reportar la exógena distrital de Bogotá", "decimal", "3500", date(2025, 1, 1), None, PV, "Resolución DDI-024115 de 2026 (Secretaría Distrital de Hacienda), según prensa especializada: 3.500 UVT; verificar en la resolución"),
    ("PUC_PASIVO_FINANCIERO_CORRIENTE", "Parte de las obligaciones financieras (grupo 21) que vence en menos de 12 meses, en pesos; se suma al pasivo corriente", "decimal", "", date(2025, 1, 1), None, PV, "Definir con el contador según el vencimiento de cada crédito; el balance no trae vencimientos"),
    ("PUC_IVA_GENERADO", "Prefijos de cuentas de IVA generado (separados por coma)", "lista", "", date(2025, 1, 1), None, PV, "Definir según el plan de cuentas de World Office (el plan menciona la cuenta 2408)"),
    ("PUC_IVA_DESCONTABLE", "Prefijos de cuentas de IVA descontable", "lista", "", date(2025, 1, 1), None, PV, "Definir según el plan de cuentas de World Office (el plan menciona la cuenta 2408)"),
    ("PUC_RETEFUENTE", "Prefijos de cuentas de retención en la fuente por pagar", "lista", "2365", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_RETEIVA", "Prefijos de cuentas de retención de IVA", "lista", "2367", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_INGRESOS", "Prefijos de ingresos", "lista", "4", date(2025, 1, 1), None, PV, "PUC: clase 4"),
    ("PUC_GASTOS", "Prefijos de gastos", "lista", "5", date(2025, 1, 1), None, PV, "PUC: clase 5"),
    ("PUC_COSTOS", "Prefijos de costos de ventas", "lista", "6", date(2025, 1, 1), None, PV, "PUC: clase 6"),
    ("PUC_COSTOS_GASTOS", "Prefijos de costos y gastos para la utilidad", "lista", "5,6,7", date(2025, 1, 1), None, PV, "PUC: clases 5, 6 y 7"),
    ("PUC_IMPUESTO_RENTA", "Cuentas del gasto por impuesto de renta (se excluyen de la utilidad antes de impuestos)", "lista", "5405", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_CAJA_BANCOS", "Prefijos de caja y bancos", "lista", "11", date(2025, 1, 1), None, PV, "PUC: grupo 11"),
    ("PUC_CARTERA", "Prefijos de cartera de clientes", "lista", "13", date(2025, 1, 1), None, PV, "PUC: grupo 13"),
    ("PUC_CUENTAS_POR_PAGAR", "Prefijos de proveedores y cuentas por pagar", "lista", "22,23", date(2025, 1, 1), None, PV, "PUC: grupos 22 y 23"),
    ("PUC_INVENTARIOS", "Prefijos de inventarios", "lista", "14", date(2025, 1, 1), None, PV, "PUC: grupo 14"),
    ("PUC_ACTIVO_CORRIENTE", "Prefijos del activo corriente (para liquidez)", "lista", "", date(2025, 1, 1), None, PV, "Definir con el contador"),
    ("PUC_PASIVO_CORRIENTE", "Prefijos del pasivo corriente (para liquidez)", "lista", "", date(2025, 1, 1), None, PV, "Definir con el contador"),
    ("PUC_CUENTAS_CONTRA", "Cuentas que por diseño llevan saldo contrario a su clase (depreciación acumulada, provisiones, devoluciones en ventas, IVA)", "lista", "1299,1399,1499,1592,1597,1599,4175,2408", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_NO_DEDUCIBLES", "Cuentas de gastos no deducibles", "lista", "", date(2025, 1, 1), None, PV, "Definir con el contador"),
    ("PUC_ACTIVOS_FIJOS", "Prefijos de propiedad, planta y equipo depreciable", "lista", "1524,1528,1540", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_GASTO_DEPRECIACION", "Prefijos del gasto de depreciación", "lista", "5160", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_GASTO_PERSONAL", "Prefijos del gasto de personal", "lista", "5105", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_PROVISIONES_LABORALES", "Prefijos de obligaciones laborales (cesantías, intereses, prima, vacaciones)", "lista", "25", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("CONTROL_DESDE", "Fecha de puesta en marcha: lo que venció antes se trata como histórico (sin alertas ni hallazgos)", "texto", "2026-10-01", date(2025, 1, 1), None, V, "Confirmado por la empresa el 9-oct-2026"),
    ("ALERTA_PANTALLA_DIAS", "Días de anticipación con que una obligación pendiente salta como alerta en pantalla", "decimal", "20", date(2025, 1, 1), None, V, "Decisión del dueño (9-oct-2026): alertas solo de lo que vence en los próximos 20 días"),
    ("CALENDARIO_DESDE", "Primera fecha que gestiona el calendario: no se crean obligaciones con fecha anterior", "texto", "2026-01-01", date(2025, 1, 1), None, V, "Decisión del dueño (9-oct-2026): el sistema gestiona desde 2026"),
    ("TOLERANCIA_PESOS", "Diferencia máxima tolerada por redondeo (pesos)", "decimal", "1", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("ALERTA_DIAS_ANTES", "Días antes del vencimiento en que se envía alerta", "lista", "15,7,3,1", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("ESTIMACION_UMBRAL_CAMBIO", "Cambio relativo entre meses que dispara alerta de estimación", "decimal", "0.10", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("CONCILIAR_GRUPOS", "Grupos de cuentas para conciliar auxiliares vs balance", "lista", "11,13,22,23,24", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
]

# Plan de cuentas real de World Office (balance de prueba de septiembre de 2026 entregado por el contador). Cada fila:
# (parámetro, valor, estado, nota, valores anteriores que se pueden reemplazar). Solo se reemplaza lo que sigue sin verificar y
# con el valor de fábrica: lo que alguien ya editó o verificó en la pantalla no se toca.
FUENTE_PLAN = "Plan de cuentas de World Office (balance de septiembre de 2026 entregado por el contador)"
PLAN_DE_CUENTAS = [
    ("PUC_IVA_GENERADO", "240801", V, "cuenta 240801 IVA GENERADO", {""}),
    ("PUC_IVA_DESCONTABLE", "240802", V, "cuenta 240802 IVA DESCONTABLE (incluye 24080201 compras, 24080203 servicios, 24080209 importaciones)", {""}),
    ("PUC_RETEFUENTE", "2365", V, "grupo 2365 RETENCION EN LA FUENTE", {"2365"}),
    ("PUC_RETEIVA", "2367", V, "grupo 2367 IMPUESTO A LAS VENTAS RETENIDO", {"2367"}),
    ("PUC_INGRESOS", "4", V, "clase 4 INGRESOS", {"4"}),
    ("PUC_GASTOS", "5", V, "clase 5 GASTOS", {"5"}),
    ("PUC_COSTOS", "6,7", V, "clase 6 COSTOS DE VENTAS y clase 7 COSTOS DE PRODUCCION O DE OPERACION (73 costos indirectos: arrendamientos, teléfono); el balance usa ambas", {"6", "6,7"}),
    ("PUC_COSTOS_GASTOS", "5,6,7", V, "clases 5, 6 y 7", {"5,6,7"}),
    ("PUC_CAJA_BANCOS", "1105,1110,1120", V, "1105 CAJA, 1110 BANCOS y 1120 CUENTAS DE AHORRO", {"11"}),
    ("PUC_CARTERA", "1305", V, "1305 CLIENTES (1330, 1355 y 1380 no son cartera de clientes)", {"13"}),
    ("PUC_CUENTAS_POR_PAGAR", "22,2335", V, "22 PROVEEDORES y 2335 COSTOS Y GASTOS POR PAGAR", {"22,23"}),
    ("PUC_INVENTARIOS", "14", V, "grupo 14 INVENTARIOS", {"14"}),
    ("PUC_ACTIVO_CORRIENTE", "11,13,14,1705", V, "11 DISPONIBLE, 13 DEUDORES, 14 INVENTARIOS y 1705 GASTOS PAGADOS POR ANTICIPADO (el balance no tiene inversiones del grupo 12)", {"", "11,13,14,1705"}),
    ("PUC_PASIVO_CORRIENTE", "22,23,24,25,26,28", PV, "pasivos de operación (22 a 26 y 28). Falta decidir cuáles obligaciones financieras (21, casi todo el pasivo) vencen en menos de un año: el balance no trae el vencimiento", {"", "22,23,24,25,26,28"}),
    ("PUC_ACTIVOS_FIJOS", "1512,1516,1524", V, "grupos 1512 (maquinaria, oficina, computación, flota), 1516 (edificios y oficinas) y 1524 (muebles y enseres), que tienen su depreciación acumulada en 1592; los terrenos (1504) no se deprecian", {"1524,1528,1540", "1512,1516,1524"}),
    ("PUC_GASTO_DEPRECIACION", "5160", V, "grupo 5160 DEPRECIACIONES", {"5160"}),
    ("PUC_GASTO_PERSONAL", "5105", V, "grupo 5105 GASTOS DE PERSONAL", {"5105"}),
    ("PUC_PROVISIONES_LABORALES", "25,2610", V, "25 OBLIGACIONES LABORALES y 2610 PARA OBLIGACIONES LABORALES (cesantías, intereses, vacaciones, prima)", {"25"}),
    ("PUC_NO_DEDUCIBLES", "539540", V, "539540 GASTOS NO DEDUCIBLES, la cuenta que el balance destina a ese fin", {"", "539540"}),
    ("PUC_IMPUESTO_RENTA", "5405", PV, "el balance no tiene cuentas de la clase 54: confirmar dónde se registra el gasto por impuesto de renta", {"5405"}),
    ("PUC_CUENTAS_CONTRA", "1592,4175,2408", V, "1592 DEPRECIACION ACUMULADA, 4175 DEVOLUCIONES EN VENTAS y 2408 IVA llevan saldo contrario por diseño",
     {"1299,1399,1499,1592,1597,1599,4175,2408"}),
]

FUENTE_DECRETO = "Decreto 2229 de 2023 (normograma DIAN); VenciApp y Actualícese; cálculo con festivos"
REGLAS = [
    ("retefuente", 9, 15, "regla", FUENTE_DECRETO),
    ("iva", 9, 15, "regla", FUENTE_DECRETO),
    ("renta_c1", 9, 15, "estimada", "Decreto 2229 de 2023 fija la regla; no hay lista oficial publicada para 2027"),
    ("renta_c2", 9, 15, "estimada", "Decreto 2229 de 2023 fija la regla; no hay lista oficial publicada para 2027"),
]
SDH = "Resolución SDH-000195 de 2025 (calendario tributario distrital 2026); Siempre al Día, Portafolio y Publimetro coinciden"
COMUNICADO = "Comunicado de la Secretaría Distrital de Hacienda (bogota.gov.co)"
UNA = "Una fuente (prensa sobre la Resolución SDH-000195 de 2025); confirmar con la resolución"
ICA_ANUAL_NOTA = "ICA Bogotá, declaración anual 2026 (solo régimen anual: la empresa declara bimestral; confirmar si aplica)"
# (obligación, clave, fecha, nombre, verificación, fuente). Solo fechas con fuente; no se inventan.
FIJAS = [
    ("ica", "2025-B6", date(2026, 2, 13), "ICA Bogotá, 6.º bimestre 2025 (nov-dic 2025)", "dos_fuentes", "SDH, recordatorio del 9-feb-2026, y prensa"),
    ("ica", "2026-B1", date(2026, 4, 10), "ICA Bogotá, 1.er bimestre (ene-feb 2026)", "dos_fuentes", SDH),
    ("ica", "2026-B2", date(2026, 6, 12), "ICA Bogotá, 2.º bimestre (mar-abr 2026)", "dos_fuentes", SDH),
    ("ica", "2026-B3", date(2026, 8, 21), "ICA Bogotá, 3.er bimestre (may-jun 2026)", "dos_fuentes", SDH),
    ("ica", "2026-B4", date(2026, 10, 9), "ICA Bogotá, 4.º bimestre (jul-ago 2026)", "dos_fuentes", SDH),
    ("ica", "2026-B5", date(2026, 12, 11), "ICA Bogotá, 5.º bimestre (sep-oct 2026)", "dos_fuentes", SDH),
    ("ica", "2026-B6", date(2027, 2, 12), "ICA Bogotá, 6.º bimestre (nov-dic 2026)", "dos_fuentes", SDH),
    ("ica", "2026-anual", date(2027, 2, 26), ICA_ANUAL_NOTA, "dos_fuentes", SDH),
    ("reteica", "2025-B6", date(2026, 1, 16), "ReteICA Bogotá, 6.º bimestre 2025 (nov-dic 2025)", "dos_fuentes", COMUNICADO),
    ("reteica", "2026-B1", date(2026, 3, 20), "ReteICA Bogotá, 1.er bimestre (ene-feb 2026)", "dos_fuentes", COMUNICADO),
    ("reteica", "2026-B2", date(2026, 5, 22), "ReteICA Bogotá, 2.º bimestre (mar-abr 2026)", "dos_fuentes", COMUNICADO),
    ("reteica", "2026-B3", date(2026, 7, 17), "ReteICA Bogotá, 3.er bimestre (may-jun 2026)", "dos_fuentes", COMUNICADO),
    ("reteica", "2026-B4", date(2026, 9, 18), "ReteICA Bogotá, 4.º bimestre (jul-ago 2026)", "una_fuente", UNA),
    ("reteica", "2026-B5", date(2026, 11, 20), "ReteICA Bogotá, 5.º bimestre (sep-oct 2026)", "una_fuente", UNA),
    ("reteica", "2026-B6", date(2027, 1, 15), "ReteICA Bogotá, 6.º bimestre (nov-dic 2026)", "una_fuente", UNA),
    # Información exógena: se contrasta con las fuentes; sin confirmar con los textos oficiales
    ("exogena", "2025", date(2026, 5, 28), "Información exógena DIAN, año gravable 2025 (NIT terminado en 49)", "dos_fuentes",
     "Calendario de la Resolución 000227 de 2025 (DIAN) por los dos últimos dígitos del NIT sin DV: 46 a 50 el 28-may-2026; "
     "Actualícese, Buk, Siempre al Día, CuentaTe y CIJUF coinciden. Hubo plazos extraordinarios al 31-ago-2026 solo para ciertos formatos (Res. 000021 de 2026)"),
    ("exogena_distrital", "2025", date(2026, 10, 26), "Información exógena distrital de Bogotá, año gravable 2025 (dígito 9, plataforma PIDO)", "dos_fuentes",
     "Resolución DDI-024115 del 27-jul-2026 (Secretaría Distrital de Hacienda): dígito 9 el 26-oct-2026; Infobae y Actualícese coinciden. "
     "Obligada si tuvo ingresos brutos >= 3.500 UVT en 2025 o es agente de retención del distrito: confirmar con el contador"),
]


class Command(BaseCommand):
    help = "Carga datos iniciales (empresa, parámetros, reglas de vencimiento, contratista, festivos, calendario)."

    def handle(self, *args, **opts):
        nit = "900902549"
        dv = calcular_dv(nit)
        Empresa.objects.update_or_create(
            nit=nit,
            defaults=dict(
                dv=dv, razon_social="DH TRANS-STORAGE SAS", domicilio="Bogotá D.C.",
                representante_legal="Candy Yesenia Henao Molina", revisor_fiscal="María Bernarda Lloreda Chica",
                contador="Daniel Orlando Henao Molina",
            ),
        )
        for codigo, desc, tipo, valor, desde, hasta, estado, fuente in PARAMETROS:
            Parametro.objects.get_or_create(
                codigo=codigo, vigente_desde=desde,
                defaults=dict(descripcion=desc, tipo=tipo, valor=valor, vigente_hasta=hasta, estado=estado, fuente=fuente),
            )
        for obligacion, digito, dia, verif, fuente in REGLAS:
            ReglaVencimiento.objects.get_or_create(
                obligacion=obligacion, modo="dia_habil", digito=digito, vigente_desde=date(2024, 1, 1),
                defaults=dict(dia_habil=dia, verificacion=verif, fuente=fuente,
                              descripcion=f"Día hábil {dia} para NIT terminado en {digito}"),
            )
        for tipo, clave, fecha, nombre, verif, fuente in FIJAS:
            ReglaVencimiento.objects.update_or_create(
                obligacion=tipo, modo="fecha_fija", periodo_clave=clave, vigente_desde=date(2026, 1, 1),
                defaults=dict(fecha=fecha, descripcion=nombre, verificacion=verif, fuente=fuente),
            )
        Contratista.objects.get_or_create(
            contrato="CT-0029-2026",
            defaults=dict(
                nombre="Ideako", inicio=date(2026, 10, 8), fin=date(2027, 10, 8), honorarios_mensuales=500000,
                honorarios_mas_iva=True, dias_informe=15,
                alcance="Revisión mensual y presentación de impuestos.",
                exclusiones="Registro y causación. Obligaciones incumplidas antes del inicio del servicio (8-oct-2026).",
            ),
        )
        for anio in range(2025, 2030):
            asegurar_festivos(anio)
        # Desde 2025 porque en 2026 se pagan períodos de 2025 (retención de dic-2025, IVA del 3.er cuatrimestre, renta AG 2025);
        # CALENDARIO_DESDE evita crear lo que venció antes de 2026.
        n = generar_obligaciones(2025, 2027)
        # Estado conocido a 9-oct-2026 según la empresa
        # Contrastadas con dos fuentes y el cálculo de día hábil (plan, 9-oct-2026)
        for tipo, claves in (("retefuente", ["2026-09", "2026-10", "2026-11", "2026-12"]), ("iva", ["2026-P3"])):
            Obligacion.objects.filter(tipo=tipo, clave__in=claves).update(
                verificacion="dos_fuentes", fuente="Dos fuentes (VenciApp, Actualícese) y cálculo del día hábil coinciden")
        for tipo, clave, fecha, nombre, verif, fuente in FIJAS:
            Obligacion.objects.filter(tipo=tipo, clave=clave).update(nombre=nombre, fecha_limite=fecha, verificacion=verif, fuente=fuente)
        # La empresa confirmó (9-oct-2026) que todos los impuestos con vencimiento hasta el 9-oct-2026 están presentados y pagados.
        n_hist = Obligacion.objects.filter(
            tipo__in=["retefuente", "iva", "ica", "reteica", "renta_c1", "renta_c2"], fecha_limite__lte=date(2026, 10, 9),
            estado__in=["pendiente", "en_preparacion", "presentada"],
        ).update(
            estado="pagada",
            notas="Presentada y pagada (confirmado por la empresa el 9-oct-2026). Sin evidencia cargada en el sistema.",
        )
        # Matrícula mercantil 2026: renovada el 29-abr-2026 según el certificado de la Cámara de Comercio de Bogotá (1-sep-2026)
        Obligacion.objects.filter(tipo="matricula", clave="2026").update(
            estado="pagada", verificacion="dos_fuentes",
            fuente="Certificado de existencia y representación legal, Cámara de Comercio de Bogotá, expedido el 1-sep-2026",
            notas="Matrícula renovada el 29-abr-2026 (último año renovado: 2026); los establecimientos DH LAPTOP STORAGE y DH BOOKS también figuran renovados 2026.",
        )
        Obligacion.objects.filter(tipo="exogena", clave="2025", estado__in=["pendiente", "en_preparacion"]).update(
            estado="presentada", notas="Presentada, según la empresa (9-oct-2026). Conseguir el acuse como evidencia.")
        Obligacion.objects.filter(tipo="ica", clave="2026-B4").update(
            estado="pagada", notas="Declarado y pagado, según la empresa. Conseguir el acuse como evidencia.")
        # La empresa confirmó (9-oct-2026) que Ideako presenta la retención de septiembre y la exógena distrital.
        Obligacion.objects.filter(tipo="retefuente", clave="2026-09", estado="pendiente").update(
            notas="Pendiente de presentar. Ideako la presenta, según la empresa (9-oct-2026): guardar el acuse como evidencia.")
        Obligacion.objects.filter(tipo="exogena_distrital", clave="2025", estado="pendiente", notas="").update(
            notas="Pendiente de presentar. Ideako la presenta, según la empresa (9-oct-2026): guardar el acuse como evidencia.")
        Obligacion.objects.filter(
            tipo__in=["retefuente", "exogena_distrital"], clave__in=["2026-09", "2025"], estado="pendiente", elabora="",
        ).update(elabora="Ideako")
        # Perfil del exporte real de la DIAN (libro con una hoja por mes y columna Grupo = Emitido/Recibido).
        PerfilImportacion.objects.get_or_create(
            nombre="DIAN · libro de facturas (una hoja por mes)", tipo="facturas_dian",
            defaults=dict(hoja="*", formato_fecha="%d-%m-%Y", mapeo={
                "tipo_documento": "Tipo de documento", "prefijo": "Prefijo", "numero": "Folio", "cufe": "CUFE/CUDE",
                "fecha": "Fecha Emisión", "nit_emisor": "NIT Emisor", "nombre_emisor": "Nombre Emisor",
                "nit_receptor": "NIT Receptor", "nombre_receptor": "Nombre Receptor", "iva": "IVA", "total": "Total",
                "estado_dian": "Estado", "sentido": "Grupo",
            }),
        )
        self._aplicar_plan_de_cuentas()
        self._confirmar_uvt_2025()
        asegurar_vigencias()
        self._confirmar_pasivo_financiero_2026()
        self._confirmar_tope_iva()
        self._confirmar_regimen_ordinario()
        self._confirmar_respuestas_del_dueno()
        self._recalcular_controles()
        self.stdout.write(self.style.SUCCESS(f"Datos iniciales listos. Obligaciones nuevas: {n}. Marcadas como presentadas y pagadas: {n_hist}. DV del NIT: {dv}."))

    def _recalcular_controles(self):
        """Tras una actualización las reglas pueden haber cambiado: se vuelven a ejecutar en los periodos abiertos con datos."""
        from analitica import estimaciones
        from controles.motor import ejecutar_reglas
        from empresa.models import ArchivoCargado, Periodo

        ids = set(ArchivoCargado.objects.filter(vigente=True).values_list("periodo_id", flat=True))
        for periodo in Periodo.objects.filter(id__in=ids):
            if not periodo.cerrado:
                ejecutar_reglas(periodo)
                estimaciones.recalcular(periodo)  # las advertencias de la proyección dependen de los parámetros

    def _aplicar_plan_de_cuentas(self):
        """Pone en los parámetros PUC las cuentas reales de World Office, sin pisar lo que alguien ya editó o verificó."""
        for codigo, valor, estado, nota, anteriores in PLAN_DE_CUENTAS:
            Parametro.objects.filter(codigo=codigo, vigente_hasta__isnull=True).exclude(estado=V).filter(
                valor__in=anteriores,
            ).update(valor=valor, estado=estado, fuente=f"{FUENTE_PLAN}: {nota}"[:300])  # el campo admite 300

    def _confirmar_pasivo_financiero_2026(self):
        """El dueño informó el 10-oct-2026 que ninguna obligación financiera vence en los próximos 12 meses (parte corriente = 0)."""
        Parametro.objects.filter(codigo="PUC_PASIVO_FINANCIERO_CORRIENTE", vigente_desde=date(2026, 1, 1), valor="").exclude(estado=V).update(
            valor="0", estado=V, fuente="Informado por el dueño el 10-oct-2026: ninguna deuda financiera vence en los próximos 12 meses; revisar con la contadora al cierre",
        )

    def _confirmar_regimen_ordinario(self):
        """RUT (actualización del 15-abr-2025, impreso el 17-jul-2026): responsabilidad 05, impuesto de renta régimen ordinario (no SIMPLE, que sería la 47)."""
        rut = "RUT: responsabilidad 05 (renta, régimen ordinario; sin la 47 del SIMPLE), persona jurídica"
        Parametro.objects.filter(codigo="RENTA_TARIFA", valor="0.35").exclude(estado=V).update(
            estado=V, fuente=f"Estatuto Tributario art. 240 (35 % sociedades, Ley 2277 de 2022); {rut}"[:300])
        Parametro.objects.filter(codigo="RENTA_TASA_MINIMA", valor="0.15").exclude(estado=V).update(
            estado=V, fuente=f"Estatuto Tributario art. 240 par. 6 (tasa mínima de tributación 15 %); {rut}"[:300])
        Parametro.objects.filter(codigo="RENTA_ANTICIPO_PORCENTAJE", valor="", vigente_hasta__isnull=True).update(
            valor="0.75", fuente="Estatuto Tributario art. 807: 75 % desde el tercer año de declaración (la empresa declara desde 2015); falta confirmarlo con la contadora"[:300])

    def _confirmar_respuestas_del_dueno(self):
        """Respuestas del dueño del 9 y 10-oct-2026: la contadora fijó 1110 para bancos y ninguna obligación financiera vence en 12 meses."""
        Parametro.objects.filter(codigo="PUC_CAJA_BANCOS", valor="1110").exclude(estado=V).update(
            estado=V, fuente="Confirmado por la contadora (informado por el dueño el 9-oct-2026): la cuenta de bancos es la 1110")
        Parametro.objects.filter(codigo="PUC_PASIVO_CORRIENTE", valor="22,23,24,25,26,28").exclude(estado=V).update(
            estado=V, fuente="Informado por el dueño el 10-oct-2026: ninguna obligación financiera (grupo 21) vence en menos de 12 meses, así que el corriente es 22 a 26 y 28; revisar al cierre"[:300])

    def _confirmar_tope_iva(self):
        """Estatuto Tributario art. 600: IVA bimestral con ingresos brutos del año anterior de 92.000 UVT o más; cuatrimestral para los demás."""
        Parametro.objects.filter(codigo="IVA_TOPE_BIMESTRAL_UVT", valor="92000").exclude(estado=V).update(
            estado=V, fuente="Estatuto Tributario art. 600 (bimestral desde 92.000 UVT de ingresos brutos del año anterior; cuatrimestral los demás)",
        )

    def _confirmar_uvt_2025(self):
        """UVT 2025 = $49.799 (Resolución DIAN 000193 de 2024), confirmada por la empresa el 10-oct-2026; coherente con la UVT 2026."""
        Parametro.objects.filter(codigo="UVT", vigente_desde=date(2025, 1, 1), valor="49799").exclude(estado=V).update(
            estado=V, fuente="Resolución DIAN 000193 de 2024 ($49.799); confirmada por la empresa el 10-oct-2026; la UVT 2026 sube 5,17 % sobre este valor",
        )
