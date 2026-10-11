"""Borrador del formulario 302 (ICA Bogotá): cifras inventadas con la misma estructura de una declaración presentada."""
from decimal import Decimal

import pytest

from empresa.models import Parametro
from impuestos.models import AjusteICA
from impuestos.reglas.formulario_302 import borrador_302

from .helpers import balance, periodo


def _bimestre_4():
    Parametro.objects.filter(codigo="ICA_MAPA_INGRESOS").update(valor="4=principal,41454=6399")
    julio, agosto = periodo(2026, 7), periodo(2026, 8)
    balance(julio, [
        ("41355401", "VENTA, EQUIPO DE OFICINA Y SOFTWARE 0%", 0, 0, 45000000, 45000000),
        ("41454001", "LOGISTICA Y BODEGAJE", 0, 0, 500000, 500000),
        ("42950501", "APROVECHAMIENTOS", 0, 0, 2000000, 2000000),
        ("41750101", "DEVOLUCIONES 1.VENTA, EQUIPO DE OFICINA", 0, 30000, 0, -30000),
        ("13551801", "RETENCION DE ICA POR VENTA DE PRODUCTOS 11,04", 0, 250000, 0, 250000),
    ])
    balance(agosto, [
        ("41355401", "VENTA, EQUIPO DE OFICINA Y SOFTWARE 0%", 0, 0, 50000000, 95000000),
        ("41454001", "LOGISTICA Y BODEGAJE", 0, 0, 500000, 1000000),
        ("42950501", "APROVECHAMIENTOS", 0, 0, 2000000, 4000000),
        ("41750101", "DEVOLUCIONES 1.VENTA, EQUIPO DE OFICINA", 0, 20000, 0, -50000),
        ("13551802", "RETENCION DE ICA POR VENTA DE SERVICIOS 9,66", 0, 250000, 0, 250000),
    ])
    AjusteICA.objects.create(anio=2026, bimestre=4, ingresos_fuera_distrito=Decimal("4000000"))


def renglon(r, n):
    return next(f for f in r["filas"] if f["renglon"] == n)["valor"]


@pytest.mark.django_db
def test_borrador_302_encadena_los_renglones_como_el_formulario(datos_iniciales):
    _bimestre_4()
    r = borrador_302(2026, 4)
    assert renglon(r, 9) == Decimal("100000000") and renglon(r, 10) == Decimal("4000000") and renglon(r, 11) == Decimal("96000000")
    assert renglon(r, 12) == Decimal("50000") and renglon(r, 16) == Decimal("95950000")
    principal, secundaria = r["actividades"]
    assert (principal["ciiu"], principal["base"], principal["tarifa"]) == ("4651", Decimal("94950000"), Decimal("11.040"))
    assert (secundaria["ciiu"], secundaria["base"], secundaria["tarifa"]) == ("6399", Decimal("1000000"), Decimal("9.660"))
    assert principal["base"] + secundaria["base"] == renglon(r, 16)
    assert renglon(r, 17) == Decimal("1058000")  # 94.950.000 × 11,04 ‰ + 1.000.000 × 9,66 ‰ = 1.057.908
    assert renglon(r, 18) == Decimal("159000") and renglon(r, 20) == Decimal("1217000")  # 15 % de 1.058.000 = 158.700
    assert renglon(r, 21) == Decimal("500000")  # débitos de las cuentas 135518
    assert renglon(r, 24) == Decimal("717000") and renglon(r, 25) == Decimal("717000") and renglon(r, 27) == Decimal("717000")
    avisos = " ".join(r["calculo"]["advertencias"])
    assert "por verificar con la tabla del Distrito" in avisos and "Todos los ingresos están en la actividad principal" not in avisos


@pytest.mark.django_db
def test_borrador_302_avisa_si_falta_un_balance_o_los_datos_manuales(datos_iniciales):
    balance(periodo(2026, 3), [("41355401", "VENTAS", 0, 0, 10000000, 10000000)])
    r = borrador_302(2026, 2)  # marzo-abril: solo hay marzo
    avisos = " ".join(r["calculo"]["advertencias"])
    assert "Falta el balance de 04/2026" in avisos and "No hay datos manuales" in avisos and "Todos los ingresos están en la actividad principal" in avisos
    assert renglon(r, 9) == Decimal("10000000")
    assert borrador_302(2026, 6)["filas"] == []  # sin ningún balance no se inventa nada


@pytest.mark.django_db
def test_pantalla_descargas_y_datos_manuales_del_borrador_302(cliente_dueno, datos_iniciales):
    _bimestre_4()
    url = "/ica/borrador/?anio=2026&mes=8"
    html = cliente_dueno.get(url).content.decode()
    assert "BORRADOR · NO PRESENTAR" in html and "1.217.000" in html and "Datos manuales del bimestre" in html
    pdf = cliente_dueno.get(url + "&formato=pdf")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    xlsx = cliente_dueno.get(url + "&formato=xlsx")
    assert xlsx.content[:2] == b"PK" and "borrador-302-2026-b4.xlsx" in xlsx["Content-Disposition"]
    assert "Ver y descargar borrador del formulario 302" in cliente_dueno.get("/ica/?anio=2026&mes=8").content.decode()
    form = cliente_dueno.get("/ica/datos/?anio=2026&bimestre=4")
    assert form.status_code == 200
    r = cliente_dueno.post("/ica/datos/?anio=2026&bimestre=4", {"ingresos_fuera_distrito": "6000000", "exportaciones": "0", "activos_fijos": "0",
                                                                 "deducciones": "0", "unidades_adicionales": "0", "sanciones": "0",
                                                                 "descuento": "0", "intereses_mora": "0", "nota": ""})
    assert r.status_code == 302 and AjusteICA.objects.get(anio=2026, bimestre=4).ingresos_fuera_distrito == Decimal("6000000")
