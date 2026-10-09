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
from empresa.models import Empresa, Parametro
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
    ("PUC_NO_DEDUCIBLES", "Cuentas de gastos no deducibles", "lista", "", date(2025, 1, 1), None, PV, "Definir con el contador"),
    ("PUC_ACTIVOS_FIJOS", "Prefijos de propiedad, planta y equipo depreciable", "lista", "1524,1528,1540", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_GASTO_DEPRECIACION", "Prefijos del gasto de depreciación", "lista", "5160", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_GASTO_PERSONAL", "Prefijos del gasto de personal", "lista", "5105", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("PUC_PROVISIONES_LABORALES", "Prefijos de obligaciones laborales (cesantías, intereses, prima, vacaciones)", "lista", "25", date(2025, 1, 1), None, PV, "PUC comercial; confirmar contra el plan de cuentas real"),
    ("CONTROL_DESDE", "Fecha de puesta en marcha: lo que venció antes se trata como histórico (sin alertas ni hallazgos)", "texto", "2026-10-01", date(2025, 1, 1), None, V, "Confirmado por la empresa el 9-oct-2026"),
    ("CALENDARIO_DESDE", "Primera fecha que gestiona el calendario: no se crean obligaciones con fecha anterior", "texto", "2026-01-01", date(2025, 1, 1), None, V, "Decisión del dueño (9-oct-2026): el sistema gestiona desde 2026"),
    ("TOLERANCIA_PESOS", "Diferencia máxima tolerada por redondeo (pesos)", "decimal", "1", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("ALERTA_DIAS_ANTES", "Días antes del vencimiento en que se envía alerta", "lista", "15,7,3,1", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("ESTIMACION_UMBRAL_CAMBIO", "Cambio relativo entre meses que dispara alerta de estimación", "decimal", "0.10", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
    ("CONCILIAR_GRUPOS", "Grupos de cuentas para conciliar auxiliares vs balance", "lista", "11,13,22,23,24", date(2025, 1, 1), None, V, "Criterio operativo del sistema"),
]

FUENTE_DECRETO = "Decreto 2229 de 2023 (normograma DIAN); VenciApp y Actualícese; cálculo con festivos"
REGLAS = [
    ("retefuente", 9, 15, "regla", FUENTE_DECRETO),
    ("iva", 9, 15, "regla", FUENTE_DECRETO),
    ("renta_c1", 9, 15, "estimada", "Decreto 2229 de 2023 fija la regla; no hay lista oficial publicada para 2027"),
    ("renta_c2", 9, 15, "estimada", "Decreto 2229 de 2023 fija la regla; no hay lista oficial publicada para 2027"),
]
INCP = "INCP, calendario de impuestos distritales 2026 (Resolución SDH-000195 de 2025): una fuente secundaria"
ICA_FIJAS = [
    ("2026-B4", date(2026, 10, 9), "ICA Bogotá, 4.º bimestre (jul-ago 2026)"),
    ("2026-B5", date(2026, 12, 11), "ICA Bogotá, 5.º bimestre (sep-oct 2026)"),
    ("2026-B6", date(2027, 2, 12), "ICA Bogotá, 6.º bimestre (nov-dic 2026)"),
    ("2026-anual", date(2027, 2, 26), "ICA Bogotá, declaración anual 2026"),
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
        for clave, fecha, nombre in ICA_FIJAS:
            ReglaVencimiento.objects.get_or_create(
                obligacion="ica", modo="fecha_fija", periodo_clave=clave, vigente_desde=date(2026, 1, 1),
                defaults=dict(fecha=fecha, descripcion=nombre, verificacion="una_fuente", fuente=INCP),
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
        # La empresa confirmó (9-oct-2026) que todos los impuestos con vencimiento hasta el 9-oct-2026 están presentados y pagados.
        n_hist = Obligacion.objects.filter(
            tipo__in=["retefuente", "iva", "ica", "renta_c1", "renta_c2"], fecha_limite__lte=date(2026, 10, 9),
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
        Obligacion.objects.filter(tipo="ica", clave="2026-B4").update(
            estado="pagada", notas="Declarado y pagado, según la empresa. Conseguir el acuse como evidencia.")
        Obligacion.objects.filter(tipo="retefuente", clave="2026-09", estado="pendiente").update(
            notas="Pendiente de presentar. Incluida en el servicio de Ideako: dejarlo por escrito.")
        self.stdout.write(self.style.SUCCESS(f"Datos iniciales listos. Obligaciones nuevas: {n}. Marcadas como presentadas y pagadas: {n_hist}. DV del NIT: {dv}."))
