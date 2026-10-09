from collections import defaultdict
from decimal import Decimal

from contabilidad.models import Movimiento
from empresa.models import Parametro, ParametroPendiente, Periodo
from terceros.models import Tercero

from .motor import NoAplica, Resultado, regla


def pagos_acumulados(periodo):
    """Pagos del año por tercero en cuentas de costo y gasto (clases 5, 6, 7), acumulados al periodo."""
    periodos = Periodo.objects.filter(anio=periodo.anio, mes__lte=periodo.mes)
    totales = defaultdict(Decimal)
    qs = Movimiento.objects.filter(periodo__in=periodos, archivo__vigente=True).exclude(nit="").select_related("cuenta")
    for m in qs:
        if m.cuenta.clase in ("5", "6", "7"):
            totales[m.nit] += m.debito - m.credito
    return totales


def anio_completo(periodo):
    """True si hay auxiliares vigentes de los 12 meses del año: la exógena se arma con el año gravable completo."""
    from empresa.models import ArchivoCargado

    meses = set(ArchivoCargado.objects.filter(tipo="auxiliar", periodo__anio=periodo.anio, vigente=True)
                .values_list("periodo__mes", flat=True))
    return len(meses) == 12


def sin_anio_completo(periodo):
    """Resultado «no aplica» mientras falten auxiliares de algún mes del año (None si ya se puede evaluar)."""
    if anio_completo(periodo):
        return None
    return NoAplica(f"la exógena se valida con los auxiliares de los 12 meses de {periodo.anio}, y aún no están todos cargados.")


def tope(anio):
    """Tope de reporte por tercero en pesos: parámetro EXOGENA_TOPE_PESOS o EXOGENA_TOPE_UVT × UVT."""
    from datetime import date

    fecha = date(anio, 12, 31)
    try:
        return Parametro.obtener("EXOGENA_TOPE_PESOS", fecha)
    except ParametroPendiente:
        pass
    try:
        return Parametro.obtener("EXOGENA_TOPE_UVT", fecha) * Parametro.obtener("UVT", fecha)
    except ParametroPendiente:
        return None


@regla("EXO001", "exogena", "Tercero reportable sin datos completos", "media",
       "Resolución DIAN de información exógena del año gravable: identificación, nombre, dirección y municipio")
def reportables_sin_datos(periodo):
    """Terceros que superan el tope durante el año pero no tienen los datos mínimos."""
    pendiente = sin_anio_completo(periodo)
    if pendiente:
        return pendiente
    t = tope(periodo.anio)
    if t is None:
        return [Resultado(clave="sin-tope", titulo="Falta el tope de exógena",
                          detalle="Carga EXOGENA_TOPE_PESOS (o EXOGENA_TOPE_UVT) con la resolución vigente para validar durante el año.",
                          severidad="baja")]
    salida = []
    totales = pagos_acumulados(periodo)
    for nit, total in totales.items():
        if total < t:
            continue
        tercero = Tercero.objects.filter(nit=nit).first()
        faltan = tercero.faltantes_exogena() if tercero else ["tercero no existe en el maestro"]
        if faltan:
            salida.append(Resultado(
                clave=nit, titulo=f"Tercero {nit} reportable sin datos completos",
                detalle=f"Pagos acumulados {total:,.0f} (tope {t:,.0f}); falta {', '.join(faltan)}.",
                cifras={"acumulado": total, "tope": t}))
    return salida


@regla("EXO002", "exogena", "Diferencia entre facturas y auxiliares por tercero", "baja",
       "Los valores reportados deben conciliar con la contabilidad")
def facturas_vs_auxiliares(periodo):
    """Compara la base de facturas recibidas del tercero con sus gastos y costos en los auxiliares."""
    from facturacion.models import facturas_vigentes

    pendiente = sin_anio_completo(periodo)
    if pendiente:
        return pendiente

    t = tope(periodo.anio)
    if t is None:
        return []
    por_factura = defaultdict(Decimal)
    for f in facturas_vigentes(periodo, "recibida"):
        por_factura[f.nit_emisor] += f.signo * f.subtotal
    contables = pagos_acumulados(periodo)
    salida = []
    for nit, valor in por_factura.items():
        # compara solo el mes (las facturas son del periodo): usa auxiliares del periodo
        mes = sum(
            (m.debito - m.credito for m in Movimiento.objects.filter(periodo=periodo, archivo__vigente=True, nit=nit).select_related("cuenta")
             if m.cuenta.clase in ("5", "6", "7")),
            Decimal("0"),
        )
        if contables.get(nit, 0) >= t and abs(mes - valor) > Decimal("1"):
            salida.append(Resultado(clave=nit, titulo=f"Tercero {nit}: facturas y auxiliares no coinciden",
                                    detalle=f"Facturas {valor:,.0f}; auxiliares {mes:,.0f}.",
                                    cifras={"facturas": valor, "auxiliares": mes}))
    return salida
