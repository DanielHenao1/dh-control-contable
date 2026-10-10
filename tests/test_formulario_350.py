"""Borrador del formulario 350: cifras sintéticas con la misma estructura de un caso presentado (nada es real)."""
from datetime import date
from decimal import Decimal

import pytest

from impuestos.reglas.formulario_350 import a_miles, borrador_350, tarifa_del_nombre
from terceros.models import Tercero

from .helpers import auxiliar, balance, periodo


def _datos_del_mes():
    p = periodo(2026, 8)
    balance(p, [
        ("23651502", "HONORARIOS DECLARANTES 11%", 0, 0, 13860, 13860),
        ("23653002", "ARRENDAMIENTO BIENES INMUEBLES 3,5%", 0, 0, 280000, 280000),
        ("23653501", "INTERESES POR PRESTAMO DEL 7%", 0, 705995, 252000, -453995),  # el débito es el pago del mes anterior
        ("23657501", "AUTORRETENCION DE RENTA 0,55%", 0, 0, 125634, 125634),
        ("23657502", "AUTO RETENCION RENTA EN SERVICIOS 1,10%", 0, 0, 33759, 33759),
        ("23670520", "IVA RETENIDO 15%", 0, 0, 0, 0),
    ])
    d = date(2026, 8, 10)
    Tercero.objects.create(nit="900111222", razon_social="Cliente SAS", tipo_persona="juridica")
    auxiliar(p, [
        (d, "CE", "H1", "23651502", "900222333", 0, 13860),
        (d, "CE", "A1", "23653002", "1019000001", 0, 280000),
        (d, "CE", "I1", "23653501", "1019000002", 0, 252000),
        (d, "FV", "V1", "23657501", "900111222", 0, 100634),
        (d, "FV", "V2", "23657501", "1019000003", 0, 25000),
        (d, "FV", "S1", "23657502", "900111222", 0, 24739),
        (d, "FV", "S2", "23657502", "1019000003", 0, 9020),
    ])
    return p


def fila(r, clave):
    return next(f for f in r["filas"] if f["clave"] == clave)


@pytest.mark.django_db
def test_borrador_350_reproduce_la_estructura_de_una_declaracion_presentada(datos_iniciales):
    r = borrador_350(_datos_del_mes())
    assert fila(r, "honorarios")["j"] == {"casilla_base": 29, "base": Decimal("126000"), "casilla_ret": 42, "retencion": Decimal("14000")}
    arr = fila(r, "arrendamientos")["n"]  # cédula = persona natural
    assert (arr["casilla_base"], arr["base"], arr["casilla_ret"], arr["retencion"]) == (83, Decimal("8000000"), 99, Decimal("280000"))
    ren = fila(r, "rendimientos")["n"]
    assert (ren["base"], ren["retencion"]) == (Decimal("3600000"), Decimal("252000"))
    av = fila(r, "auto_ventas")
    assert (av["j"]["casilla_base"], av["j"]["base"], av["j"]["retencion"]) == (60, Decimal("18297000"), Decimal("101000"))
    assert (av["n"]["casilla_ret"], av["n"]["retencion"]) == (121, Decimal("25000"))
    asv = fila(r, "auto_servicios")
    assert (asv["j"]["base"], asv["j"]["retencion"], asv["n"]["base"], asv["n"]["retencion"]) == (Decimal("2249000"), Decimal("25000"), Decimal("820000"), Decimal("9000"))
    assert r["total_renta"] == Decimal("706000") and r["total_retenciones"] == Decimal("706000")
    assert r["valores"]["debitos_del_balance"] == Decimal("705995")  # no se restan
    assert any("se dedujo por el NIT" in a for a in r["calculo"]["advertencias"])  # las cédulas no están en el maestro


@pytest.mark.django_db
def test_borrador_350_sin_auxiliar_y_con_cuentas_sin_mapa(datos_iniciales):
    p = periodo(2026, 7)
    balance(p, [("23659999", "OTRA RETENCION RARA", 0, 0, 5000, 5000)])
    r = borrador_350(p)
    avisos = " ".join(r["calculo"]["advertencias"])
    assert "Sin libro auxiliar" in avisos and "23659999" in avisos and "Sin tarifa" in avisos
    assert fila(r, "otros_pagos")["j"]["retencion"] == Decimal("5000")  # aproximado a miles


def test_funciones_auxiliares_del_borrador():
    assert a_miles(Decimal("100634")) == Decimal("101000") and a_miles(Decimal("499")) == Decimal("0") and a_miles(Decimal("500")) == Decimal("1000")
    assert tarifa_del_nombre("ARRENDAMIENTO BIENES INMUEBLES 3,5%") == Decimal("3.5")
    assert tarifa_del_nombre("RETENCION POR COMPRAS DIFERIDOS") is None


@pytest.mark.django_db
def test_pantalla_y_descargas_del_borrador_350(cliente_dueno, datos_iniciales):
    _datos_del_mes()
    url = "/retencion/borrador/?anio=2026&mes=8"
    html = cliente_dueno.get(url).content.decode()
    assert "BORRADOR · NO PRESENTAR" in html and "706" in html
    pdf = cliente_dueno.get(url + "&formato=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    xlsx = cliente_dueno.get(url + "&formato=xlsx")
    assert xlsx.content[:2] == b"PK" and "borrador-350-2026-08.xlsx" in xlsx["Content-Disposition"]
    assert "Ver y descargar borrador" in cliente_dueno.get("/retencion/?anio=2026&mes=8").content.decode()


@pytest.mark.django_db
def test_la_retencion_contable_es_la_practicada_del_mes(datos_iniciales):
    from impuestos.reglas.retencion import borrador_retefuente

    p = _datos_del_mes()
    assert borrador_retefuente(p).valores["contabilidad"] == Decimal("705253")  # créditos, sin restar el pago del mes anterior
