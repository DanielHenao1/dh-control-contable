from datetime import date

from empresa.models import Parametro, Periodo
from facturacion.models import Factura, facturas_vigentes
from impuestos.models import Declaracion

from .comun import CERO, Calculo, movimiento_neto, total_clase


def tramos_iva(periodicidad):
    if periodicidad == "bimestral":
        return [(1, 2), (3, 4), (5, 6), (7, 8), (9, 10), (11, 12)]
    return [(1, 4), (5, 8), (9, 12)]


def periodicidad_vigente(anio):
    return Parametro.obtener_o("IVA_PERIODICIDAD", "cuatrimestral", fecha=date(anio, 6, 1))


def tramo_de(anio, mes):
    tramos = tramos_iva(periodicidad_vigente(anio))
    for i, (a, b) in enumerate(tramos, start=1):
        if a <= mes <= b:
            return i, a, b
    raise ValueError("mes inválido")


def iva_facturas(anio, mes_ini, mes_fin):
    """IVA generado (emitidas) y descontable (recibidas) de las facturas DIAN vigentes."""
    generado = descontable = CERO
    ingresos = compras = CERO
    for mes in range(mes_ini, mes_fin + 1):
        p = Periodo.objects.filter(anio=anio, mes=mes).first()
        if not p:
            continue
        for f in facturas_vigentes(p):
            if f.tipo_documento == Factura.TipoDocumento.DOC_SOPORTE and f.sentido == "emitida":
                continue
            if f.sentido == Factura.Sentido.EMITIDA:
                generado += f.signo * f.iva
                ingresos += f.signo * f.subtotal
            else:
                descontable += f.signo * f.iva
                compras += f.signo * f.subtotal
    return generado, descontable, ingresos, compras


def iva_contabilidad(anio, mes_ini, mes_fin, calculo=None):
    """IVA generado y descontable según las cuentas del balance (parámetros PUC_IVA_*)."""
    calculo = calculo or Calculo()
    gen = Calculo()
    pref_gen = gen.usar("PUC_IVA_GENERADO")
    pref_des = gen.usar("PUC_IVA_DESCONTABLE")
    calculo.advertencias += gen.advertencias
    generado = descontable = None
    if pref_gen and pref_des:
        generado = descontable = CERO
        for mes in range(mes_ini, mes_fin + 1):
            p = Periodo.objects.filter(anio=anio, mes=mes).first()
            if p:
                generado += movimiento_neto(p, pref_gen, "C")
                descontable += movimiento_neto(p, pref_des, "D")
    return generado, descontable


def borrador_iva(anio, indice):
    """Borrador propio de IVA del período; nunca para presentar."""
    c = Calculo()
    tramos = tramos_iva(periodicidad_vigente(anio))
    mes_ini, mes_fin = tramos[indice - 1]
    gen, des, ingresos, compras = iva_facturas(anio, mes_ini, mes_fin)
    c.valores.update({
        "iva_generado": gen, "iva_descontable": des, "saldo": gen - des,
        "ingresos_gravados_fe": ingresos, "compras_fe": compras,
        "meses": f"{mes_ini}-{mes_fin}",
    })
    c.supuestos += [
        "IVA generado = IVA de facturas emitidas menos notas crédito (DIAN).",
        "IVA descontable = IVA de facturas recibidas; se asume 100% descontable (sin prorrateo ni exclusiones).",
        "No incluye saldos a favor de períodos anteriores ni retenciones de IVA practicadas.",
    ]
    if gen == 0 and des == 0:
        c.advertencias.append("No hay facturas cargadas para el período: el borrador está en cero.")
    return c


def declarado_iva(anio, indice):
    d = Declaracion.objects.filter(tipo="iva", anio=anio, indice=indice).first()
    return d.valor_declarado if d and d.valor_declarado is not None else None


def ingresos_brutos_anio(anio):
    """Ingresos brutos del año (clase 4) según el último balance del año."""
    from .comun import ultimo_balance

    p = ultimo_balance(anio)
    if p is None:
        return None, None
    pref = Parametro.obtener_o("PUC_INGRESOS", ["4"])
    return total_clase(p, pref), p
