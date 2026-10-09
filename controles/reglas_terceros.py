from contabilidad.models import movimientos_vigentes
from facturacion.models import facturas_vigentes
from terceros.models import Tercero

from .motor import Resultado, regla


def _nits_del_periodo(periodo):
    nits = set(movimientos_vigentes(periodo).exclude(nit="").values_list("nit", flat=True))
    for f in facturas_vigentes(periodo):
        nits.update([f.nit_emisor, f.nit_receptor])
    return {n for n in nits if n}


@regla("TER001", "terceros", "Dígito de verificación errado", "media", "Estatuto Tributario art. 555-1; Resolución DIAN de DV (módulo 11)")
def dv_errado(periodo):
    """El DV del maestro debe coincidir con el calculado por el algoritmo de la DIAN."""
    salida = []
    for t in Tercero.objects.filter(nit__in=_nits_del_periodo(periodo)).exclude(dv=""):
        if not t.dv_correcto and len(t.nit) >= 8:
            salida.append(Resultado(
                clave=t.nit, titulo=f"DV errado para el NIT {t.nit}",
                detalle=f"{t.razon_social}: figura {t.dv}, el cálculo da {t.dv_calculado}.",
                cifras={"registrado": t.dv, "calculado": t.dv_calculado},
            ))
    return salida


@regla("TER002", "terceros", "Datos incompletos para exógena", "baja", "Resolución DIAN de información exógena: identificación, nombre, dirección y municipio")
def datos_incompletos(periodo):
    """Terceros movidos en el periodo sin los datos mínimos que exige la exógena."""
    salida = []
    for t in Tercero.objects.filter(nit__in=_nits_del_periodo(periodo)):
        faltan = t.faltantes_exogena()
        if faltan:
            salida.append(Resultado(
                clave=t.nit, titulo=f"Tercero {t.nit} con datos incompletos",
                detalle=f"{t.razon_social or '(sin nombre)'}: falta {', '.join(faltan)}.", cifras={"faltantes": faltan},
            ))
    return salida


@regla("TER003", "terceros", "Tercero de facturas ausente del maestro", "media", "Control interno")
def tercero_fuera_del_maestro(periodo):
    """Facturas DIAN cuyo tercero no existe en el maestro."""
    en_maestro = set(Tercero.objects.values_list("nit", flat=True))
    salida, vistos = [], set()
    for f in facturas_vigentes(periodo):
        nit = f.nit_tercero
        if nit and nit not in en_maestro and nit not in vistos:
            vistos.add(nit)
            salida.append(Resultado(clave=nit, titulo=f"Tercero {nit} de facturas no está en el maestro",
                                    detalle=f"Aparece en la factura {f.numero_completo}."))
    return salida


@regla("TER004", "terceros", "Tercero duplicado por razón social", "baja", "Control interno")
def terceros_duplicados(periodo):
    """Misma razón social con NIT distinto (posible tercero duplicado)."""
    por_nombre = {}
    for t in Tercero.objects.filter(nit__in=_nits_del_periodo(periodo)).exclude(razon_social=""):
        por_nombre.setdefault(t.razon_social.strip().lower(), []).append(t.nit)
    return [
        Resultado(clave=nombre, titulo=f"Posible tercero duplicado: {nombre}", detalle=f"NIT: {', '.join(nits)}")
        for nombre, nits in por_nombre.items() if len(nits) > 1
    ]
