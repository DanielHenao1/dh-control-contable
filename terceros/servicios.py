"""Qué terceros tienen movimiento en los archivos vigentes y cuáles quedaron sueltos (por ejemplo, tras borrar una carga de prueba)."""
from contabilidad.models import Movimiento
from facturacion.models import Factura
from impuestos.models import Retencion

from .models import Tercero


def nits_con_movimiento(anio=None):
    """NIT que aparecen en facturas, movimientos o retenciones de archivos vigentes (de un año, o de todos)."""
    filtro = {"archivo__vigente": True}
    if anio:
        filtro["periodo__anio"] = anio
    nits = set(Movimiento.objects.filter(**filtro).exclude(nit="").values_list("nit", flat=True).distinct())
    nits |= set(Retencion.objects.filter(**filtro).values_list("nit", flat=True).distinct())
    facturas = Factura.objects.filter(**filtro)
    nits |= set(facturas.values_list("nit_emisor", flat=True).distinct())
    nits |= set(facturas.values_list("nit_receptor", flat=True).distinct())
    return nits


def sin_movimiento():
    """Terceros que ya no aparecen en ningún archivo vigente."""
    con = nits_con_movimiento()
    return [t for t in Tercero.objects.all() if t.nit not in con]


def anios_con_datos():
    from empresa.models import Periodo

    return sorted(set(Periodo.objects.values_list("anio", flat=True)), reverse=True)
