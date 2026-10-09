from datetime import date
from decimal import Decimal

import pytest

from analitica import estimaciones
from analitica.models import Estimacion
from analitica.servicios import (
    anomalias_periodo,
    atipicos_iqr,
    atipicos_mad,
    benford_primer_digito,
    indicadores_mes,
    proyectar_serie,
    suavizado_exponencial,
)
from empresa.models import Parametro

from .helpers import auxiliar, balance, factura, periodo


def test_atipicos():
    vals = [100, 102, 98, 101, 99, 100, 5000]
    assert atipicos_iqr(vals) == [6]
    assert atipicos_mad(vals) == [6]
    assert atipicos_iqr([1, 2]) == []


def test_benford():
    # Sucesión de potencias de 2 sigue Benford; números que empiezan todos por 9 no
    potencias = [2**k for k in range(1, 400)]
    r = benford_primer_digito(potencias)
    assert r["suficiente"] and not r["desviado"]
    r2 = benford_primer_digito([9000 + i for i in range(200)])
    assert r2["desviado"]
    assert not benford_primer_digito([10, 20])["suficiente"]


def test_proyeccion_con_banda():
    p = proyectar_serie([100, 110, 90, 105], 3)
    assert p["metodo"].startswith("suavizado") and len(p["proyeccion"]) == 3
    assert all(lo <= x <= hi for lo, x, hi in zip(p["minimo"], p["proyeccion"], p["maximo"]))
    assert p["maximo"][2] - p["minimo"][2] > p["maximo"][0] - p["minimo"][0]  # la banda crece
    est = proyectar_serie([10, 20], 2, serie_anio_anterior=[10, 10, 10, 20])
    assert est["metodo"].startswith("promedio estacional")
    assert est["proyeccion"] == [15.0, 30.0]
    assert suavizado_exponencial([]) == (None, None)


@pytest.mark.django_db
def test_indicadores_y_anomalias(datos_iniciales):
    p = periodo(2026, 6)
    balance(p, [
        ("1105", "Caja", 0, 0, 0, 1000), ("2205", "Proveedores", 0, 0, 0, 400),
        ("4135", "Ventas", 0, 0, 5000, 5000), ("6135", "Costo", 0, 2000, 0, 2000), ("5195", "Gastos", 0, 1000, 0, 1000),
    ])
    r = indicadores_mes(p)
    a = r["actual"]
    assert a["ingresos"] == Decimal("5000") and a["utilidad"] == Decimal("2000")
    assert a["margen_neto"] == Decimal("0.4") and a["endeudamiento"] == Decimal("0.4")
    assert any("PUC_ACTIVO_CORRIENTE" in x for x in r["advertencias"])
    filas = [(date(2026, 6, 1 + i % 20), "C", f"D{i}", "5195", "900111", 100 + i % 3, 0) for i in range(30)]
    filas.append((date(2026, 6, 2), "C", "DX", "5195", "900111", 90000, 0))
    auxiliar(p, filas)
    an = anomalias_periodo(p)
    assert any(x["valor"] == 90000 for x in an["por_cuenta"])


def cargar_anio(mes_fin, ingreso_mensual=1_000_000, gasto_mensual=600_000):
    """Balances acumulados con resultados lineales."""
    for m in range(1, mes_fin + 1):
        p = periodo(2026, m)
        balance(p, [
            ("4135", "Ventas", 0, 0, ingreso_mensual, ingreso_mensual * m),
            ("5195", "Gastos", 0, gasto_mensual, 0, gasto_mensual * m),
            ("1105", "Caja", 0, 0, 0, 2_000_000 + 100_000 * m),
        ])


@pytest.mark.django_db
def test_estimacion_de_renta(datos_iniciales):
    cargar_anio(9)
    corte = periodo(2026, 9)
    r = estimaciones.recalcular(corte)
    base = r["renta"]["base"]
    # utilidad anual = 400.000 × 12 = 4.800.000 → 35 % = 1.680.000 (serie constante => sin banda)
    assert base["valor"] == Decimal("1680000")
    assert base["minimo"] == base["maximo"] == Decimal("1680000")
    assert Estimacion.objects.filter(impuesto="renta", escenario="adverso").exists()
    assert any("por verificar" in a for a in base["advertencias"])


@pytest.mark.django_db
def test_renta_amplia_rango_con_diferencias_sin_explicar(datos_iniciales):
    from impuestos.models import DiferenciaFiscal

    cargar_anio(9)
    DiferenciaFiscal.objects.create(anio=2026, concepto="Multas", tipo="perm_mas", valor=Decimal("1000000"))
    r = estimaciones.estimar_renta(2026, periodo(2026, 9))
    base = r["base"]
    assert base["maximo"] - base["minimo"] == Decimal("700000")  # 1.000.000 × 35 % a cada lado


@pytest.mark.django_db
def test_renta_sin_tarifa_queda_pendiente(datos_iniciales):
    Parametro.objects.filter(codigo="RENTA_TARIFA").update(valor="")
    cargar_anio(3)
    r = estimaciones.estimar_renta(2026, periodo(2026, 3))
    assert r["base"]["valor"] is None
    assert any("RENTA_TARIFA" in a for a in r["base"]["advertencias"])


@pytest.mark.django_db
def test_estimacion_iva_y_caja(datos_iniciales):
    cargar_anio(9)
    p = periodo(2026, 9)
    for m in (9,):
        factura(periodo(2026, m), "emitida", "1", date(2026, 9, 5), "900902549", "800111", 1000, 190)
        factura(periodo(2026, m), "recibida", "1", date(2026, 9, 6), "900111", "900902549", 500, 95)
    r = estimaciones.estimar_iva(2026, p)
    assert r["base"]["supuestos"]["real_a_la_fecha"] == Decimal("95")
    caja, adv = estimaciones.caja_proyectada(p, 3)
    assert caja[0] == Decimal("2900000") and caja[1] == Decimal("3000000")
    estimaciones.recalcular(p)
    c = estimaciones.caja_de_impuestos(p)
    assert c["filas"]


@pytest.mark.django_db
def test_alerta_cuando_el_impuesto_supera_la_caja(datos_iniciales):
    cargar_anio(9)
    # caja casi vacía
    from contabilidad.models import SaldoCuenta

    SaldoCuenta.objects.filter(cuenta__codigo="1105").update(saldo_final=Decimal("1000"))
    p = periodo(2026, 9)
    estimaciones.recalcular(p)
    alertas = estimaciones.alertas_estimacion(p)
    assert any("supera la caja" in a for a in alertas)


@pytest.mark.django_db
def test_simulador(datos_iniciales):
    cargar_anio(9)
    p = periodo(2026, 9)
    estimaciones.recalcular(p)
    r = estimaciones.simular(p, {"gastos_planeados": 1_000_000, "provision_cartera": 200_000})
    assert r["utilidad_simulada"] == r["utilidad_base"] - Decimal("1200000")
    # la provisión no es deducible: el impuesto solo baja por los gastos (1.000.000 × 35 %)
    assert r["variacion_impuesto"] == Decimal("-350000")
    assert any("no deducible" in a for a in r["advertencias"])
    assert estimaciones.simular(periodo(2026, 2), {})["error"]


@pytest.mark.django_db
def test_comparativo_y_notas(datos_iniciales):
    from analitica.servicios import comparativo_clases

    balance(periodo(2025, 6), [("4135", "Ventas", 0, 0, 1000, 1000), ("1105", "Caja", 0, 0, 0, 500)])
    balance(periodo(2026, 6), [("4135", "Ventas", 0, 0, 1500, 1500), ("1105", "Caja", 0, 0, 0, 500)])
    r = comparativo_clases(periodo(2026, 6))
    ingresos = next(f for f in r["filas"] if f["clase"] == "4")
    assert ingresos["var_anio"] == Decimal("0.5")
    assert any("aumentó 50%" in n for n in r["notas"])
