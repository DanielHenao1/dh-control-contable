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


def indice_por_nombre():
    """Nombre normalizado -> NIT, solo para nombres que identifican a un único tercero del maestro (los repetidos se omiten)."""
    from controles.reglas_facturas import norm_nombre

    vistos, repetidos = {}, set()
    for t in Tercero.objects.exclude(razon_social="").only("nit", "razon_social"):
        clave = norm_nombre(t.razon_social)
        if not clave:
            continue
        if clave in vistos and vistos[clave] != t.nit:
            repetidos.add(clave)
        vistos[clave] = t.nit
    return {k: v for k, v in vistos.items() if k not in repetidos}


def vincular_movimientos(usuario=None):
    """Pone el NIT del maestro en los movimientos que solo traen el nombre del tercero (el auxiliar de World Office no trae NIT)."""
    from controles.reglas_facturas import norm_nombre
    from empresa.models import RegistroAuditoria

    indice = indice_por_nombre()
    if not indice:
        return {"movimientos": 0, "nombres": 0}
    pendientes = Movimiento.objects.filter(nit="").exclude(tercero_nombre="")
    nombres = {}
    for nombre in pendientes.values_list("tercero_nombre", flat=True).distinct():
        nit = indice.get(norm_nombre(nombre))
        if nit:
            nombres[nombre] = nit
    movimientos = 0
    for nombre, nit in nombres.items():
        movimientos += pendientes.filter(tercero_nombre=nombre).update(nit=nit)
    if movimientos:
        RegistroAuditoria.registrar(
            "modificar", descripcion=f"NIT del maestro de terceros puesto en {movimientos} movimientos ({len(nombres)} nombres)",
            detalle={"movimientos": movimientos, "nombres": len(nombres)}, usuario=usuario,
        )
    return {"movimientos": movimientos, "nombres": len(nombres)}
