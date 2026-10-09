"""Proyección de impuestos del año y simulador de cierre ("qué pasa si").

Son estimaciones de gestión: las cifras salen de las mismas reglas deterministas de los borradores,
con los parámetros vigentes. La IA no calcula. Cada resultado guarda sus supuestos y advertencias.
"""
from datetime import date
from decimal import Decimal

from calendario.models import Obligacion
from contabilidad.models import saldos_vigentes
from empresa.models import Parametro, Periodo
from impuestos.models import DiferenciaFiscal
from impuestos.reglas.comun import CERO, Calculo, total_clase
from impuestos.reglas.ica import tarifa_ica
from impuestos.reglas.iva import iva_facturas, tramo_de
from impuestos.reglas.renta import borrador_renta, resultado_contable
from impuestos.reglas.retencion import borrador_retefuente

from .models import Estimacion
from .servicios import proyectar_serie

ESCENARIOS = ("base", "favorable", "adverso")


def _dec(x):
    return None if x is None else Decimal(str(round(x)))


def _utilidades_mensuales(anio, hasta_mes):
    """Utilidad de cada mes como diferencia de acumulados (el balance de pérdidas y ganancias es acumulado)."""
    acum, previo, serie = [], CERO, []
    for mes in range(1, hasta_mes + 1):
        p = Periodo.objects.filter(anio=anio, mes=mes).first()
        if p and saldos_vigentes(p).exists():
            u = resultado_contable(p)["utilidad_antes_impuestos"]
            serie.append(u - previo)
            previo = u
            acum.append(u)
    return serie


def estimar_renta(anio, corte):
    c0 = Calculo()
    real = borrador_renta(anio, corte)
    serie = _utilidades_mensuales(anio, corte.mes)
    previa = _utilidades_mensuales(anio - 1, 12) or None
    restantes = 12 - corte.mes
    advert = list(real.advertencias)
    if not serie:
        return {e: dict(valor=None, minimo=None, maximo=None, supuestos={}, advertencias=advert) for e in ESCENARIOS}
    proy = proyectar_serie(serie, restantes, previa)
    acumulado = resultado_contable(corte, c0)["utilidad_antes_impuestos"]
    totales = {
        "base": acumulado + sum(Decimal(str(x)) for x in proy["proyeccion"]),
        "favorable": acumulado + sum(Decimal(str(x)) for x in proy["minimo"]),
        "adverso": acumulado + sum(Decimal(str(x)) for x in proy["maximo"]),
    }
    impuestos = {}
    for e, u in totales.items():
        r = borrador_renta(anio, corte, utilidad_proyectada=u)
        impuestos[e] = r.valores.get("impuesto_estimado")
        advert += r.advertencias
    ancho = CERO
    if real.valores.get("diferencias_sin_explicar") and real.valores.get("tarifa") is not None:
        ancho = sum((abs(d.valor) for d in DiferenciaFiscal.objects.filter(anio=anio, explicada=False)), CERO) * real.valores["tarifa"]
    base = impuestos["base"]
    salida = {}
    for e in ESCENARIOS:
        v = impuestos[e]
        salida[e] = dict(
            valor=v,
            minimo=None if impuestos["favorable"] is None else impuestos["favorable"] - ancho,
            maximo=None if impuestos["adverso"] is None else impuestos["adverso"] + ancho,
            supuestos={"metodo": proy["metodo"], "utilidad_proyectada_anual": totales[e],
                       "meses_reales": corte.mes, "meses_proyectados": restantes,
                       "notas": real.supuestos},
            advertencias=sorted(set(advert)),
        )
    if base is None:
        for e in salida:
            salida[e]["valor"] = None
    return salida


def estimar_iva(anio, corte):
    indice, mes_ini, mes_fin = tramo_de(anio, corte.mes)
    gen_s, des_s = [], []
    for m in range(mes_ini, corte.mes + 1):
        g, d, _, _ = iva_facturas(anio, m, m)
        gen_s.append(g)
        des_s.append(d)
    restantes = mes_fin - corte.mes
    neto = [g - d for g, d in zip(gen_s, des_s)]
    proy = proyectar_serie(neto, restantes)
    real = sum(neto, CERO)
    advert = []
    if not any(gen_s) and not any(des_s):
        advert.append("No hay facturas cargadas del período en curso.")
    out = {}
    for e, clave in (("base", "proyeccion"), ("favorable", "minimo"), ("adverso", "maximo")):
        total = real + sum((Decimal(str(x)) for x in proy[clave]), CERO)
        out[e] = dict(valor=total, minimo=real + sum((Decimal(str(x)) for x in proy["minimo"]), CERO),
                      maximo=real + sum((Decimal(str(x)) for x in proy["maximo"]), CERO),
                      supuestos={"metodo": proy["metodo"], "periodo": f"{mes_ini}-{mes_fin}/{anio}", "indice": indice,
                                 "real_a_la_fecha": real},
                      advertencias=advert + (["Saldo a favor en el período en curso."] if total < 0 else []))
    return out


def estimar_retefuente(anio, corte):
    previos = []
    for m in range(max(1, corte.mes - 3), corte.mes):
        p = Periodo.objects.filter(anio=anio, mes=m).first()
        if p:
            v = borrador_retefuente(p).valores
            previos.append(v.get("contabilidad") if v.get("contabilidad") is not None else v.get("retenido_registrado"))
    actual = borrador_retefuente(corte)
    valor = actual.valores.get("contabilidad")
    if valor is None:
        valor = actual.valores.get("retenido_registrado")
    vals = [float(x) for x in previos if x is not None]
    media = sum(vals) / len(vals) if vals else None
    out = {}
    for e in ESCENARIOS:
        out[e] = dict(
            valor=valor, minimo=valor, maximo=valor,
            supuestos={"mes": str(corte), "promedio_meses_anteriores": None if media is None else round(media),
                       "meses_comparados": len(vals)},
            advertencias=actual.advertencias,
        )
    return out


def estimar_ica(anio, corte):
    c = Calculo()
    ciiu = c.usar("ICA_ACTIVIDAD_PRINCIPAL")
    tarifa = tarifa_ica(ciiu, date(anio, corte.mes, 1)) if ciiu else None
    if not tarifa or tarifa.tarifa_por_mil is None:
        c.advertencias.append("Falta la tarifa de ICA de la actividad principal.")
        return {e: dict(valor=None, minimo=None, maximo=None, supuestos={}, advertencias=sorted(set(c.advertencias))) for e in ESCENARIOS}
    pref = c.usar("PUC_INGRESOS", defecto=["4"]) or ["4"]
    serie = []
    previo = CERO
    for m in range(1, corte.mes + 1):
        p = Periodo.objects.filter(anio=anio, mes=m).first()
        if p and saldos_vigentes(p).exists():
            a = total_clase(p, pref)
            serie.append(a - previo)
            previo = a
    proy = proyectar_serie(serie, 12 - corte.mes)
    mil = tarifa.tarifa_por_mil / Decimal("1000")
    out = {}
    for e, clave in (("base", "proyeccion"), ("favorable", "minimo"), ("adverso", "maximo")):
        ingresos = previo + sum((Decimal(str(x)) for x in proy[clave]), CERO)
        out[e] = dict(valor=(ingresos * mil).quantize(Decimal("1")),
                      minimo=((previo + sum((Decimal(str(x)) for x in proy["minimo"]), CERO)) * mil).quantize(Decimal("1")),
                      maximo=((previo + sum((Decimal(str(x)) for x in proy["maximo"]), CERO)) * mil).quantize(Decimal("1")),
                      supuestos={"metodo": proy["metodo"], "tarifa_por_mil": tarifa.tarifa_por_mil, "ingresos_anuales": ingresos},
                      advertencias=sorted(set(c.advertencias)))
    return out


ESTIMADORES = {"renta": estimar_renta, "iva": estimar_iva, "retefuente": estimar_retefuente, "ica": estimar_ica}


def recalcular(corte: Periodo):
    """Recalcula y guarda las estimaciones de los cuatro impuestos al cierre del año."""
    anio = corte.anio
    resultados = {}
    for impuesto, fn in ESTIMADORES.items():
        r = fn(anio, corte)
        resultados[impuesto] = r
        for escenario, d in r.items():
            Estimacion.objects.update_or_create(
                impuesto=impuesto, anio=anio, corte=corte, escenario=escenario,
                defaults=dict(valor=d["valor"], minimo=d["minimo"], maximo=d["maximo"],
                              supuestos=_json(d["supuestos"]), advertencias=d["advertencias"]),
            )
    return resultados


def _json(valor):
    import json

    return json.loads(json.dumps(valor, default=str))


def caja_actual(corte):
    c = Calculo()
    pref = c.usar("PUC_CAJA_BANCOS")
    if not pref:
        return None, c.advertencias
    return total_clase(corte, pref), c.advertencias


def caja_proyectada(corte, meses):
    """Caja actual + variación mensual promedio de los últimos 3 meses (lineal, referencial)."""
    actual, adv = caja_actual(corte)
    if actual is None:
        return None, adv
    pref = Calculo().usar("PUC_CAJA_BANCOS")
    valores = []
    for m in range(max(1, corte.mes - 3), corte.mes + 1):
        p = Periodo.objects.filter(anio=corte.anio, mes=m).first()
        if p and saldos_vigentes(p).exists():
            valores.append(total_clase(p, pref))
    var = (valores[-1] - valores[0]) / (len(valores) - 1) if len(valores) > 1 else CERO
    return [actual + var * i for i in range(meses + 1)], adv


def caja_de_impuestos(corte):
    """Calendario de pagos de los próximos 12 meses con montos estimados frente a la caja proyectada."""
    est = {i: {e.escenario: e for e in Estimacion.objects.filter(impuesto=i, anio=corte.anio, corte=corte)} for i in ESTIMADORES}
    proyectada, adv = caja_proyectada(corte, 12)
    filas = []
    hoy_ref = date(corte.anio, corte.mes, 1)
    obligaciones = Obligacion.objects.filter(fecha_limite__gte=hoy_ref, fecha_limite__lte=date(corte.anio + 1, corte.mes, 28)).exclude(
        estado__in=["presentada", "pagada"], laboral=True
    ).filter(laboral=False)
    media_ret = None
    if est["retefuente"].get("base") and est["retefuente"]["base"].supuestos.get("promedio_meses_anteriores") is not None:
        media_ret = Decimal(str(est["retefuente"]["base"].supuestos["promedio_meses_anteriores"]))
    for o in obligaciones.order_by("fecha_limite"):
        monto, nota = None, ""
        if o.tipo == "retefuente":
            monto = est["retefuente"]["base"].valor if est["retefuente"].get("base") and o.clave == f"{corte.anio}-{corte.mes:02d}" else media_ret
            nota = "mes en curso" if o.clave == f"{corte.anio}-{corte.mes:02d}" else "promedio de meses anteriores"
        elif o.tipo == "iva" and est["iva"].get("base"):
            if o.clave == f"{corte.anio}-P{tramo_de(corte.anio, corte.mes)[0]}":
                monto, nota = est["iva"]["base"].valor, "período en curso"
        elif o.tipo in ("renta_c1", "renta_c2") and est["renta"].get("base") and est["renta"]["base"].valor is not None:
            monto, nota = est["renta"]["base"].valor / 2, "50% del impuesto estimado (supuesto: dos cuotas iguales)"
        mes_idx = (o.fecha_limite.year - corte.anio) * 12 + o.fecha_limite.month - corte.mes
        caja = proyectada[mes_idx] if proyectada and 0 <= mes_idx < len(proyectada) else None
        filas.append({"obligacion": o, "monto": monto, "nota": nota, "caja_proyectada": caja,
                      "alerta": bool(monto is not None and caja is not None and monto > caja)})
    return {"filas": filas, "advertencias": adv}


def alertas_estimacion(corte):
    """Alertas de gestión derivadas de las estimaciones del corte."""
    alertas = []
    umbral = Parametro.obtener_o("ESTIMACION_UMBRAL_CAMBIO", Decimal("0.10"))
    ant_anio, ant_mes = corte.anterior()
    previo = Periodo.objects.filter(anio=ant_anio, mes=ant_mes).first()
    for e in Estimacion.objects.filter(anio=corte.anio, corte=corte, escenario="base"):
        if e.impuesto == "iva" and e.valor is not None and e.valor < 0:
            alertas.append(f"IVA: saldo a favor estimado en el período en curso ({e.valor:,.0f}).")
        if previo and e.valor is not None:
            p = Estimacion.objects.filter(impuesto=e.impuesto, anio=corte.anio, corte=previo, escenario="base").first()
            if p and p.valor and abs(e.valor - p.valor) / abs(p.valor) > Decimal(str(umbral)):
                alertas.append(f"{e.impuesto}: la estimación cambió {((e.valor - p.valor) / abs(p.valor)):+.0%} frente al mes anterior.")
        if e.impuesto == "renta":
            for a in e.advertencias:
                if "tasa mínima" in a:
                    alertas.append("Renta: " + a)
    for f in caja_de_impuestos(corte)["filas"]:
        if f["alerta"]:
            alertas.append(f"{f['obligacion'].nombre} {f['obligacion'].periodo_texto}: impuesto estimado {f['monto']:,.0f} supera la caja proyectada ({f['caja_proyectada']:,.0f}).")
    return alertas


def simular(corte: Periodo, ajustes: dict):
    """Efecto de decisiones de cierre sobre utilidad, renta y caja. Estimación; revisar con el contador."""
    a = {k: Decimal(str(ajustes.get(k, 0) or 0)) for k in (
        "ingresos_adelantar", "ingresos_diferir", "gastos_planeados", "compra_activos",
        "cartera_castigar", "provision_cartera", "pagos_pendientes_causar")}
    base = Estimacion.objects.filter(impuesto="renta", anio=corte.anio, corte=corte, escenario="base").first()
    sup = (base.supuestos if base else {})
    u0 = sup.get("utilidad_proyectada_anual")
    advert = list(base.advertencias) if base else ["No hay estimación de renta: recalcúlala primero."]
    if u0 is None:
        return {"error": "Sin estimación base de renta.", "advertencias": advert}
    u0 = Decimal(str(u0))
    d_util = a["ingresos_adelantar"] - a["ingresos_diferir"] - a["gastos_planeados"] - a["pagos_pendientes_causar"] \
        - a["cartera_castigar"] - a["provision_cartera"]
    # La provisión general de cartera no es deducible: se devuelve como diferencia para efectos fiscales.
    d_fiscal = d_util + a["provision_cartera"]
    u1 = u0 + d_util
    r0 = borrador_renta(corte.anio, corte, utilidad_proyectada=u0)
    # Para aislar la parte fiscal, se aplica el ajuste fiscal sobre la utilidad base
    r1 = borrador_renta(corte.anio, corte, utilidad_proyectada=u0 + d_fiscal)
    i0, i1 = r0.valores.get("impuesto_estimado"), r1.valores.get("impuesto_estimado")
    advert += r1.advertencias
    if a["compra_activos"]:
        advert.append("La compra de activos reduce caja pero la depreciación no se incluye: el efecto fiscal no se simula.")
    if a["cartera_castigar"]:
        advert.append("El castigo de cartera solo es deducible si cumple los requisitos del Estatuto Tributario; confirmar con el contador.")
    if a["provision_cartera"]:
        advert.append("La provisión general de cartera se trató como no deducible (se suma de nuevo en la conciliación fiscal).")
    delta_imp = None if i0 is None or i1 is None else i1 - i0
    return {
        "utilidad_base": u0, "utilidad_simulada": u1, "impuesto_base": i0, "impuesto_simulado": i1,
        "variacion_impuesto": delta_imp,
        "variacion_caja": None if delta_imp is None else -(delta_imp) - a["compra_activos"] - a["gastos_planeados"] - a["pagos_pendientes_causar"] + a["ingresos_adelantar"] - a["ingresos_diferir"],
        "advertencias": sorted(set(advert)),
        "nota": "Estimación de gestión. Las decisiones con efecto tributario se revisan con el contador antes de ejecutarlas.",
    }
