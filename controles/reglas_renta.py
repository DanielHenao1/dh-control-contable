from decimal import Decimal

from contabilidad.models import movimientos_vigentes
from impuestos.models import DiferenciaFiscal
from impuestos.reglas.renta import borrador_renta

from .motor import Resultado, regla


@regla("REN001", "renta", "Diferencias contable-fiscal sin explicar", "media",
       "Estatuto Tributario art. 772-1 y Decreto 1998 de 2017: conciliación fiscal (formato 2516)")
def diferencias_sin_explicar(periodo):
    """Diferencias registradas sin soporte o sin marcar como explicadas."""
    if periodo.mes != 12:
        return None
    return [
        Resultado(clave=str(d.id), titulo=f"Diferencia sin explicar: {d.concepto}",
                  detalle=f"{d.get_tipo_display()} por {d.valor:,.0f}.", cifras={"valor": d.valor})
        for d in DiferenciaFiscal.objects.filter(anio=periodo.anio)
        if not d.explicada or not d.soporte
    ]


@regla("REN002", "renta", "Tasa efectiva bajo la tasa mínima de tributación", "alta",
       "Estatuto Tributario art. 240 par. 6 (tasa mínima de tributación)")
def tasa_minima(periodo):
    """La tasa efectiva estimada no debe quedar por debajo de la tasa mínima."""
    c = borrador_renta(periodo.anio, periodo)
    v = c.valores
    if v.get("tasa_efectiva") is None or v.get("tasa_minima") is None:
        return []
    if v["tasa_efectiva"] < v["tasa_minima"]:
        return [Resultado(clave=str(periodo.anio), titulo="Tasa efectiva estimada bajo la mínima",
                          detalle=f"Tasa efectiva {v['tasa_efectiva']:.1%} vs mínima {v['tasa_minima']:.1%}. Referencial: la fórmula exacta usa utilidad depurada.",
                          cifras={"efectiva": v["tasa_efectiva"], "minima": v["tasa_minima"]})]
    return []


@regla("REN003", "renta", "Gastos y costos sin documento soporte", "media",
       "Estatuto Tributario art. 771-2 y 107: la deducción exige soporte")
def gastos_sin_soporte(periodo):
    """Movimientos de gasto o costo sin número de documento."""
    total, n = Decimal("0"), 0
    for m in movimientos_vigentes(periodo):
        if m.cuenta.clase in ("5", "6", "7") and not m.documento and m.debito > 0:
            total += m.debito
            n += 1
    if n:
        return [Resultado(clave=str(periodo), titulo=f"{n} movimiento(s) de gasto o costo sin documento",
                          detalle=f"Suman {total:,.0f}; revisar su soporte antes de deducirlos.",
                          cifras={"movimientos": n, "valor": total})]
    return []


@regla("REN004", "renta", "Gastos no deducibles sin registrar como diferencia", "media",
       "Estatuto Tributario art. 115, 107-1, 105: gastos no deducibles aumentan la renta líquida")
def no_deducibles(periodo):
    """Cuentas marcadas como no deducibles (parámetro PUC_NO_DEDUCIBLES) sin diferencia fiscal registrada."""
    from contabilidad.models import saldos_vigentes
    from impuestos.reglas.comun import Calculo, hojas

    c = Calculo()
    pref = c.usar("PUC_NO_DEDUCIBLES")
    if not pref or periodo.mes != 12:
        return None if periodo.mes != 12 else []
    total = sum((s.saldo_final for s in hojas(saldos_vigentes(periodo)) if any(s.cuenta.codigo.startswith(p) for p in pref)), Decimal("0"))
    registrado = sum((d.valor for d in DiferenciaFiscal.objects.filter(anio=periodo.anio, tipo="perm_mas")), Decimal("0"))
    if total > registrado + Decimal("1"):
        return [Resultado(clave=str(periodo.anio), titulo="Gastos no deducibles sin reflejar en la conciliación fiscal",
                          detalle=f"Cuentas marcadas: {total:,.0f}; diferencias permanentes registradas: {registrado:,.0f}.",
                          cifras={"cuentas": total, "registrado": registrado})]
    return []
