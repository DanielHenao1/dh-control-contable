from decimal import Decimal

from impuestos.models import ConceptoRetencion
from impuestos.reglas.retencion import (
    borrador_retefuente,
    calcular_teorico,
    declarado_retefuente,
    retenciones_vigentes,
)
from terceros.models import Tercero

from .motor import Resultado, regla

TOL = Decimal("1")


def _contexto(periodo):
    rets = list(retenciones_vigentes(periodo))
    terceros = {t.nit: t for t in Tercero.objects.filter(nit__in={r.nit for r in rets})}
    return rets, terceros


@regla("RET001", "retencion", "Retenido distinto del valor teórico", "alta",
       "Estatuto Tributario art. 365 y ss. y Decreto 1625 de 2016: base mínima, tarifa por concepto y condición del tercero")
def retenido_vs_teorico(periodo):
    """Recalcula la retención de cada pago y la compara con la practicada."""
    rets, terceros = _contexto(periodo)
    salida = []
    for r in rets:
        t, motivo = calcular_teorico(r, terceros=terceros)
        if t is None:
            continue
        if abs(t - r.retenido) > TOL:
            if t == 0 and r.retenido > 0 and motivo:
                continue  # lo cubre RET002
            salida.append(Resultado(
                clave=f"{r.documento}|{r.nit}|{r.concepto}|{r.base}",
                titulo=f"Retención distinta de la teórica en {r.documento or r.nit}",
                detalle=f"Concepto {r.concepto}, base {r.base:,.0f}: retenido {r.retenido:,.0f}, teórico {t:,.0f}.",
                cifras={"retenido": r.retenido, "teorico": t, "diferencia": r.retenido - t}))
    return salida


@regla("RET002", "retencion", "Retención practicada bajo la base mínima", "media",
       "La retención solo procede si la base supera el mínimo en UVT del concepto")
def bajo_base_minima(periodo):
    """Retención practicada sobre pagos que no alcanzan la base mínima."""
    rets, terceros = _contexto(periodo)
    salida = []
    for r in rets:
        t, motivo = calcular_teorico(r, terceros=terceros)
        if t == 0 and r.retenido > 0 and motivo == "base inferior al mínimo en UVT":
            salida.append(Resultado(
                clave=f"{r.documento}|{r.nit}|{r.concepto}|{r.base}",
                titulo=f"Se retuvo bajo la base mínima en {r.documento or r.nit}",
                detalle=f"Concepto {r.concepto}, base {r.base:,.0f}; retenido {r.retenido:,.0f}.",
                cifras={"retenido": r.retenido}))
    return salida


@regla("RET003", "retencion", "Tarifa aplicada distinta de la vigente", "media",
       "Tarifa por concepto y condición del tercero (declarante o no)")
def tarifa_distinta(periodo):
    """Compara la tarifa registrada con la tarifa vigente del concepto."""
    rets, terceros = _contexto(periodo)
    salida = []
    for r in rets:
        concepto = ConceptoRetencion.vigente(r.concepto, r.fecha)
        if not concepto or not r.tarifa_aplicada:
            continue
        t = terceros.get(r.nit)
        tarifa = concepto.tarifa_para(t.es_declarante if t else None)
        if tarifa is not None and abs(tarifa - r.tarifa_aplicada) > Decimal("0.001"):
            salida.append(Resultado(
                clave=f"{r.documento}|{r.nit}|{r.concepto}|{r.base}",
                titulo=f"Tarifa {r.tarifa_aplicada}% aplicada; la vigente es {tarifa}%",
                detalle=f"Concepto {r.concepto}, documento {r.documento}.",
                cifras={"aplicada": r.tarifa_aplicada, "vigente": tarifa}))
    return salida


@regla("RET004", "retencion", "Concepto de retención sin tarifa cargada", "baja", "Sin tarifa verificada no se puede recalcular")
def concepto_sin_tarifa(periodo):
    """Conceptos presentes en los pagos que no existen en el catálogo de tarifas."""
    rets, _ = _contexto(periodo)
    salida = []
    for codigo in sorted({r.concepto for r in rets}):
        if not any(ConceptoRetencion.vigente(codigo, r.fecha) for r in rets if r.concepto == codigo):
            salida.append(Resultado(clave=codigo, titulo=f"Concepto {codigo} sin tarifa cargada",
                                    detalle="Cárgalo en Configuración > Conceptos de retención con su base en UVT y tarifa."))
    return salida


@regla("RET005", "retencion", "Retención registrada distinta de la contabilidad", "alta",
       "El valor retenido por pagos debe coincidir con la cuenta de retención por pagar")
def registrada_vs_contabilidad(periodo):
    """Suma de retenciones por pago frente al movimiento de la cuenta de retención en la fuente."""
    c = borrador_retefuente(periodo)
    contable = c.valores.get("contabilidad")
    if contable is None or not c.valores.get("pagos"):
        return []
    registrado = c.valores["retenido_registrado"]
    if abs(registrado - contable) > TOL:
        return [Resultado(clave=str(periodo), titulo="Retención por pagos vs cuenta contable",
                          detalle=f"Por pagos {registrado:,.0f}; contabilidad {contable:,.0f}; diferencia {registrado - contable:,.0f}.",
                          cifras={"pagos": registrado, "contabilidad": contable, "diferencia": registrado - contable})]
    return []


@regla("RET006", "retencion", "Retención contable distinta de la declarada", "alta",
       "Conciliación mensual de retención en la fuente con el formulario 350")
def contabilidad_vs_declarado(periodo):
    """Cuenta de retención del mes frente a lo declarado por el contratista."""
    declarado = declarado_retefuente(periodo)
    if declarado is None:
        return []
    c = borrador_retefuente(periodo)
    contable = c.valores.get("contabilidad")
    base = contable if contable is not None else c.valores.get("retenido_registrado")
    if base is not None and abs(base - declarado) > TOL:
        return [Resultado(clave=str(periodo), titulo="Retención contable vs declarada",
                          detalle=f"Propio {base:,.0f}; declarado {declarado:,.0f}; diferencia {base - declarado:,.0f}.",
                          cifras={"propio": base, "declarado": declarado, "diferencia": base - declarado})]
    return []
