from decimal import ROUND_HALF_UP, Decimal

from contabilidad.models import SaldoCuenta
from empresa.models import Parametro, ParametroPendiente
from impuestos.models import ConceptoRetencion, Declaracion, Retencion
from terceros.models import Tercero

from .comun import CERO, Calculo, hojas, movimiento_neto


def redondear(valor):
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def calcular_teorico(ret, uvt=None, terceros=None):
    """Retención teórica de un pago: 0 si la base no llega al mínimo en UVT, base × tarifa si llega.

    Devuelve (valor | None, motivo). None = no se puede calcular (falta concepto, tarifa o UVT).
    """
    concepto = ConceptoRetencion.vigente(ret.concepto, ret.fecha)
    if concepto is None:
        return None, f"Concepto {ret.concepto} sin tarifa cargada"
    if uvt is None:
        try:
            uvt = Parametro.obtener("UVT", ret.fecha)
        except ParametroPendiente:
            return None, f"Falta la UVT vigente para {ret.fecha:%Y}"
    tercero = (terceros or {}).get(ret.nit)
    declarante = tercero.es_declarante if tercero else None
    tarifa = concepto.tarifa_para(declarante)
    if tarifa is None:
        return None, f"Concepto {ret.concepto} sin tarifa para la condición del tercero"
    if concepto.base_minima_uvt is not None and ret.base < concepto.base_minima_uvt * uvt:
        return CERO, "base inferior al mínimo en UVT"
    return redondear(ret.base * tarifa / Decimal("100")), ""


def retenciones_vigentes(periodo):
    return Retencion.objects.filter(periodo=periodo, archivo__vigente=True)


def borrador_retefuente(periodo):
    c = Calculo()
    rets = list(retenciones_vigentes(periodo))
    terceros = {t.nit: t for t in Tercero.objects.filter(nit__in={r.nit for r in rets})}
    teorico, sin_calcular = CERO, 0
    for r in rets:
        t, _ = calcular_teorico(r, terceros=terceros)
        if t is None:
            sin_calcular += 1
        else:
            teorico += t
    retenido = sum((r.retenido for r in rets), CERO)
    c.valores.update({"retenido_registrado": retenido, "teorico": teorico, "pagos": len(rets), "sin_calcular": sin_calcular})
    c.supuestos.append("La retención teórica usa el concepto, la tarifa y la base mínima vigentes cargados en el sistema.")
    if sin_calcular:
        c.advertencias.append(f"{sin_calcular} pago(s) sin concepto/tarifa cargada: no se pudieron recalcular.")
    if not rets:
        c.advertencias.append("No hay retenciones cargadas para el período.")
    pref = c.usar("PUC_RETEFUENTE", periodo.fin)
    contable = movimiento_neto(periodo, pref, "C") if pref else None
    c.valores["contabilidad"] = contable
    return c


def declarado_retefuente(periodo):
    d = Declaracion.objects.filter(tipo="retefuente", anio=periodo.anio, indice=periodo.mes).first()
    return d.valor_declarado if d and d.valor_declarado is not None else None


def reteiva_contable(periodo):
    pref = Parametro.obtener_o("PUC_RETEIVA")
    return movimiento_neto(periodo, pref, "C") if pref else None


def saldo_cuentas(periodo, prefijos):
    qs = SaldoCuenta.objects.filter(periodo=periodo, archivo__vigente=True).select_related("cuenta")
    return sum((s.saldo_final for s in hojas(qs) if any(s.cuenta.codigo.startswith(p) for p in prefijos)), CERO)
