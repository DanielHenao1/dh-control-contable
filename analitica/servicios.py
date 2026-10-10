"""Indicadores, anomalías y proyecciones por niveles. Todo determinista y explicable."""
import math
import statistics
from collections import Counter
from decimal import Decimal

from contabilidad.models import Movimiento, saldos_vigentes
from empresa.models import Parametro, Periodo
from impuestos.reglas.comun import CERO, Calculo, total_clase


def _div(a, b):
    return None if not b else (a / b)


# ---------- Nivel 1: indicadores del mes ----------
def indicadores_mes(periodo):
    """Indicadores clave con el mismo mes del año anterior como comparativo."""
    if not saldos_vigentes(periodo).exists():
        return {}
    c = Calculo()
    ac = c.usar("PUC_ACTIVO_CORRIENTE") or []
    pc = c.usar("PUC_PASIVO_CORRIENTE") or []
    cartera = c.usar("PUC_CARTERA") or []
    prov = c.usar("PUC_CUENTAS_POR_PAGAR") or []
    ing_pref = c.usar("PUC_INGRESOS", defecto=["4"]) or ["4"]
    cos_pref = c.usar("PUC_COSTOS", defecto=["6"]) or ["6"]
    gas_pref = c.usar("PUC_GASTOS", defecto=["5"]) or ["5"]

    def calcular(p):
        if p is None or not saldos_vigentes(p).exists():
            return {}
        ingresos = total_clase(p, ing_pref)
        costos = total_clase(p, cos_pref)
        gastos = total_clase(p, gas_pref)
        activo = total_clase(p, ["1"])
        pasivo = total_clase(p, ["2"])
        r = {
            "ingresos": ingresos, "costos": costos, "gastos": gastos,
            "utilidad": ingresos - costos - gastos, "activo_total": activo, "pasivo_total": pasivo,
            "margen_bruto": _div(ingresos - costos, ingresos),
            "margen_neto": _div(ingresos - costos - gastos, ingresos),
            "endeudamiento": _div(pasivo, activo),
        }
        if ac and pc:
            # Las obligaciones financieras (21) solo cuentan como corrientes por la parte que vence en menos de 12 meses.
            financiero = Parametro.obtener_o("PUC_PASIVO_FINANCIERO_CORRIENTE", CERO, fecha=p.fin) or CERO
            r["liquidez"] = _div(total_clase(p, ac), total_clase(p, pc) + financiero)
        if cartera:
            r["rotacion_cartera_dias"] = _div(total_clase(p, cartera) * Decimal(30 * p.mes), ingresos)
        if prov:
            r["rotacion_proveedores_dias"] = _div(total_clase(p, prov) * Decimal(30 * p.mes), costos + gastos)
        return r

    anterior = Periodo.objects.filter(anio=periodo.anio - 1, mes=periodo.mes).first()
    return {"actual": calcular(periodo), "anio_anterior": calcular(anterior), "advertencias": sorted(set(c.advertencias))}


# ---------- Nivel 2: anomalías ----------
def atipicos_iqr(valores, k=Decimal("1.5")):
    """Índices de valores fuera de [Q1 - k·IQR, Q3 + k·IQR]."""
    if len(valores) < 4:
        return []
    q1, _, q3 = statistics.quantiles([float(v) for v in valores], n=4)
    iqr = q3 - q1
    lo, hi = q1 - float(k) * iqr, q3 + float(k) * iqr
    return [i for i, v in enumerate(valores) if float(v) < lo or float(v) > hi]


def atipicos_mad(valores, umbral=3.5):
    """Puntaje z robusto (mediana y MAD); devuelve índices con |z| > umbral."""
    if len(valores) < 4:
        return []
    xs = [float(v) for v in valores]
    med = statistics.median(xs)
    mad = statistics.median([abs(x - med) for x in xs])
    if mad == 0:
        return []
    return [i for i, x in enumerate(xs) if abs(0.6745 * (x - med) / mad) > umbral]


def benford_primer_digito(valores, minimo=100):
    """Distribución del primer dígito vs ley de Benford. Requiere >= `minimo` valores."""
    primeros = []
    for v in valores:
        v = abs(Decimal(v))
        if v >= 1:
            primeros.append(int(str(int(v))[0]))
    n = len(primeros)
    if n < minimo:
        return {"suficiente": False, "n": n}
    cuenta = Counter(primeros)
    filas, chi2 = [], 0.0
    for d in range(1, 10):
        esperado = math.log10(1 + 1 / d)
        observado = cuenta.get(d, 0) / n
        chi2 += n * (observado - esperado) ** 2 / esperado
        filas.append({"digito": d, "observado": observado, "esperado": esperado})
    # valor crítico chi-cuadrado con 8 g.l. al 5% = 15.507
    return {"suficiente": True, "n": n, "chi2": chi2, "critico_5pct": 15.507, "desviado": chi2 > 15.507, "filas": filas}


def anomalias_periodo(periodo):
    """Valores atípicos por cuenta y por tercero dentro del mes."""
    movs = list(Movimiento.objects.filter(periodo=periodo, archivo__vigente=True).select_related("cuenta"))
    salida = {"por_cuenta": [], "por_tercero": [], "benford": benford_primer_digito([m.debito or m.credito for m in movs])}
    por_cuenta = {}
    for m in movs:
        por_cuenta.setdefault(m.cuenta.codigo, []).append(m)
    for codigo, lista in por_cuenta.items():
        vals = [m.debito or m.credito for m in lista]
        idx = set(atipicos_iqr(vals)) & set(atipicos_mad(vals))
        for i in sorted(idx):
            m = lista[i]
            salida["por_cuenta"].append({"cuenta": codigo, "fecha": m.fecha, "documento": m.documento,
                                         "valor": vals[i], "tercero": m.tercero_nombre or m.nit})
    por_tercero = {}
    for m in movs:
        if m.nit:
            por_tercero[m.nit] = por_tercero.get(m.nit, CERO) + (m.debito or m.credito)
    nits = list(por_tercero)
    totales = [por_tercero[n] for n in nits]
    for i in sorted(set(atipicos_iqr(totales)) & set(atipicos_mad(totales))):
        salida["por_tercero"].append({"nit": nits[i], "total": totales[i]})
    return salida


# ---------- Nivel 3: proyecciones ----------
def suavizado_exponencial(serie, alfa=0.4):
    """Suavizado exponencial simple. Devuelve (pronóstico siguiente, desviación de errores)."""
    if not serie:
        return None, None
    nivel = float(serie[0])
    errores = []
    for x in serie[1:]:
        errores.append(float(x) - nivel)
        nivel = alfa * float(x) + (1 - alfa) * nivel
    sd = statistics.pstdev(errores) if len(errores) > 1 else (abs(errores[0]) if errores else 0.0)
    return nivel, sd


def promedio_estacional(historia_anio_anterior, serie_actual, meses_restantes):
    """Estima los meses restantes con el mismo mes del año anterior escalado por el ritmo del año actual."""
    if not historia_anio_anterior or not serie_actual:
        return None
    n = len(serie_actual)
    base_prev = sum(float(x) for x in historia_anio_anterior[:n])
    base_act = sum(float(x) for x in serie_actual)
    factor = base_act / base_prev if base_prev else 1.0
    return [float(x) * factor for x in historia_anio_anterior[n:n + meses_restantes]]


def proyectar_serie(serie_actual, meses_restantes, serie_anio_anterior=None):
    """Proyección con banda de incertidumbre. Método: estacional si hay año anterior; si no, suavizado."""
    if not serie_actual:
        return {"metodo": "sin datos", "proyeccion": [], "minimo": [], "maximo": []}
    est = promedio_estacional(serie_anio_anterior, serie_actual, meses_restantes) if serie_anio_anterior else None
    nivel, sd = suavizado_exponencial(serie_actual)
    if est and len(est) == meses_restantes:
        metodo, proy = "promedio estacional escalado por el ritmo del año", est
    else:
        metodo, proy = "suavizado exponencial simple", [nivel] * meses_restantes
    banda = [1.96 * (sd or 0) * math.sqrt(i + 1) for i in range(meses_restantes)]
    return {"metodo": metodo, "proyeccion": proy, "minimo": [p - b for p, b in zip(proy, banda)],
            "maximo": [p + b for p, b in zip(proy, banda)], "sd_historica": sd}


def serie_mensual(anio, hasta_mes, prefijos, naturaleza="C"):
    """Movimiento mensual de un grupo de cuentas (positivo según naturaleza) usando balances del año."""
    from impuestos.reglas.comun import movimiento_neto

    serie = []
    for mes in range(1, hasta_mes + 1):
        p = Periodo.objects.filter(anio=anio, mes=mes).first()
        serie.append(movimiento_neto(p, prefijos, naturaleza) if p and saldos_vigentes(p).exists() else None)
    return serie


# ---------- Estados financieros: comparativos y notas de apoyo ----------
CLASES = [("1", "Activo"), ("2", "Pasivo"), ("3", "Patrimonio"), ("4", "Ingresos"), ("5", "Gastos"), ("6", "Costos de ventas"), ("7", "Costos de producción")]


def comparativo_clases(periodo):
    """Totales por clase del PUC contra el mes anterior y el mismo mes del año anterior, con notas de apoyo."""
    prev = Periodo.objects.filter(anio=periodo.anterior()[0], mes=periodo.anterior()[1]).first()
    anio_ant = Periodo.objects.filter(anio=periodo.anio - 1, mes=periodo.mes).first()

    def tot(p, clase):
        return total_clase(p, [clase]) if p and saldos_vigentes(p).exists() else None

    filas, notas = [], []
    for clase, nombre in CLASES:
        actual, mes_ant, anio_prev = tot(periodo, clase), tot(prev, clase), tot(anio_ant, clase)
        if actual is None:
            continue
        var_mes = _div(actual - mes_ant, abs(mes_ant)) if mes_ant else None
        var_anio = _div(actual - anio_prev, abs(anio_prev)) if anio_prev else None
        filas.append({"clase": clase, "nombre": nombre, "actual": actual, "mes_anterior": mes_ant, "anio_anterior": anio_prev,
                      "var_mes": var_mes, "var_anio": var_anio})
        if var_anio is not None and abs(var_anio) >= Decimal("0.2"):
            notas.append(f"{nombre}: {'aumentó' if var_anio > 0 else 'disminuyó'} {abs(var_anio):.0%} frente al mismo mes del año anterior; revisar a qué se debe.")
    ing = next((f for f in filas if f["clase"] == "4"), None)
    if ing and ing["anio_anterior"] is None:
        notas.append("No hay balance del mismo mes del año anterior: sin comparativo anual.")
    return {"filas": filas, "notas": notas}
