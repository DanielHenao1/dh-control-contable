from decimal import Decimal

from empresa.models import Periodo
from impuestos.models import DiferenciaFiscal

from .comun import CERO, Calculo, total_clase, ultimo_balance


def resultado_contable(periodo, calculo=None):
    """Utilidad contable antes de impuestos acumulada al corte (ingresos - costos y gastos).

    Usa saldos finales de hojas del balance; ingresos (clase 4) en positivo, costos y gastos
    (clases 5, 6 y 7) en positivo. Excluye la cuenta de impuesto de renta (parámetro PUC_IMPUESTO_RENTA).
    """
    calculo = calculo or Calculo()
    ing_pref = calculo.usar("PUC_INGRESOS", defecto=["4"]) or ["4"]
    gasto_pref = calculo.usar("PUC_COSTOS_GASTOS", defecto=["5", "6", "7"]) or ["5", "6", "7"]
    renta_pref = calculo.usar("PUC_IMPUESTO_RENTA", defecto=[]) or []
    ingresos = total_clase(periodo, ing_pref)
    gastos = total_clase(periodo, gasto_pref)
    impuesto_contab = total_clase(periodo, renta_pref) if renta_pref else CERO
    utilidad = ingresos - (gastos - impuesto_contab)
    return {"ingresos": ingresos, "costos_gastos": gastos - impuesto_contab, "utilidad_antes_impuestos": utilidad}


def diferencias(anio):
    mas = menos = CERO
    sin_explicar = []
    for d in DiferenciaFiscal.objects.filter(anio=anio):
        if d.efecto >= 0:
            mas += d.efecto
        else:
            menos += -d.efecto
        if not d.explicada or not d.soporte:
            sin_explicar.append(d)
    return mas, menos, sin_explicar


def borrador_renta(anio, corte: Periodo = None, utilidad_proyectada=None):
    """Impuesto de renta estimado del año con las mismas reglas deterministas.

    Si `utilidad_proyectada` viene dada (proyección a diciembre) se usa en lugar de la acumulada.
    """
    c = Calculo()
    corte = corte or ultimo_balance(anio)
    if corte is None:
        c.advertencias.append("No hay balance cargado del año: no se puede estimar la renta.")
        return c
    base = resultado_contable(corte, c)
    utilidad = base["utilidad_antes_impuestos"] if utilidad_proyectada is None else utilidad_proyectada
    mas, menos, sin_explicar = diferencias(anio)
    renta_liquida = utilidad + mas - menos
    tarifa = c.usar("RENTA_TARIFA", fecha=corte.fin)
    impuesto = None
    if tarifa is not None and renta_liquida > 0:
        impuesto = (renta_liquida * tarifa).quantize(Decimal("1"))
    elif tarifa is not None:
        impuesto = CERO
    tasa_efectiva = (impuesto / utilidad) if (impuesto is not None and utilidad > 0) else None
    tasa_min = c.usar("RENTA_TASA_MINIMA", fecha=corte.fin)
    c.valores.update({
        "corte": str(corte), "ingresos": base["ingresos"], "costos_gastos": base["costos_gastos"],
        "utilidad_contable": utilidad, "diferencias_mas": mas, "diferencias_menos": menos,
        "renta_liquida_estimada": renta_liquida, "tarifa": tarifa, "impuesto_estimado": impuesto,
        "tasa_efectiva": tasa_efectiva, "tasa_minima": tasa_min,
    })
    if tasa_efectiva is not None and tasa_min is not None and tasa_efectiva < tasa_min:
        c.advertencias.append(
            "La tasa efectiva estimada queda por debajo de la tasa mínima de tributación: revisar el impuesto a adicionar con el contador."
        )
    pct = c.usar("RENTA_ANTICIPO_PORCENTAJE", fecha=corte.fin)
    if pct is not None and impuesto is not None:
        c.valores["anticipo_referencial"] = (impuesto * pct).quantize(Decimal("1"))
    if sin_explicar:
        c.advertencias.append(
            f"{len(sin_explicar)} diferencia(s) contable-fiscal sin explicar o sin soporte: el rango de la estimación se amplía."
        )
    c.valores["diferencias_sin_explicar"] = len(sin_explicar)
    c.supuestos += [
        "Utilidad contable = ingresos (clase 4) menos costos y gastos (clases 5, 6 y 7) acumulados al último balance.",
        "Renta líquida = utilidad + diferencias que aumentan - diferencias que disminuyen (conciliación fiscal vs contable).",
        "No incluye compensación de pérdidas, rentas exentas, descuentos, retenciones ni saldos a favor: confirmar con el contador.",
    ]
    return c
