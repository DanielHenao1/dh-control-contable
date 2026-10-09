"""Libro auxiliar jerárquico de World Office, extracto de Bancolombia en PDF y filtro de perfiles por tipo."""
import io
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from weasyprint import HTML

from empresa import importacion
from empresa.forms import CargaForm
from empresa.lectores_reales import leer_auxiliar_world_office, leer_extracto_bancolombia_pdf
from empresa.models import PerfilImportacion

D = Decimal
ENC = ["Cuenta", "Tercero", "Fecha", "Nota", "Cheque", "Doc Num", "Debitos", "Creditos", "Saldo"]


def auxiliar(descuadre=0):
    f = pd.Timestamp
    filas = [
        ["EMPRESA DE PRUEBA SAS"] + [None] * 8, ["Libro Auxiliar entre el 01/09/2026 y el 30/09/2026"] + [None] * 8,
        [None] * 9, ENC,
        ["11050501 CAJA GENERAL", None, f("2026-08-31"), "SALDO INICIAL", None, None, 1000.5, 0, 1000.5],
        [None, "PROVEEDOR UNO SAS", f("2026-09-02"), "PAGO FC # 10", None, "(DTS) CE  5315", 0, 300, 700.5],
        [None, "CLIENTE DOS SAS", f("2026-09-05"), "ABONO", None, "(DTS) RC 77", 200, 0, 900.5],
        ["Total 11050501 CAJA GENERAL", None, None, None, None, None, 1200.5, 300, 900.5],
        ["52150501 AVISOS Y TABLEROS 15%_x000D_\n(SIN DEDUCCIÓN)", None, f("2026-08-31"), "SALDO INICIAL", None, None, 50, 0, 50],
        [None, "HACIENDA", f("2026-09-30"), "ICA", None, "(DTS) NC 2566", 100, 0, 150],
        ["Total 52150501 AVISOS", None, None, None, None, None, 150 + descuadre, 0, 150],
        ["Total general", None, None, None, None, None, 1350.5, 300, None],
        ["Total Movimientos Débito y Crédito", None, None, None, None, None, 300 + 0, 300, None],
    ]
    b = io.BytesIO()
    pd.DataFrame(filas).to_excel(b, header=False, index=False)
    return b.getvalue()


def test_auxiliar_propaga_cuenta_ignora_saldo_inicial_y_cuadra():
    lec = leer_auxiliar_world_office(auxiliar())
    assert lec is not None and not lec.bloqueos
    assert [(f["cuenta"], f["debito"], f["credito"]) for f in lec.filas] == [
        ("11050501", D("0.00"), D("300.00")), ("11050501", D("200.00"), D("0.00")), ("52150501", D("100.00"), D("0.00")),
    ]
    assert lec.filas[0]["tercero_nombre"] == "PROVEEDOR UNO SAS" and lec.filas[0]["comprobante"] == "CE"
    assert lec.filas[2]["cuenta_nombre"] == "AVISOS Y TABLEROS 15% (SIN DEDUCCIÓN)"  # nombre con salto de línea
    assert lec.info["ignoradas_detalle"]["saldos_iniciales"] == 2 and lec.info["totales_cuadran"]


def test_auxiliar_que_no_cuadra_con_su_total_bloquea():
    lec = leer_auxiliar_world_office(auxiliar(descuadre=50))
    assert lec.bloqueos and "52150501" in lec.bloqueos[0]


def test_auxiliar_plano_no_usa_el_lector_jerarquico():
    plano = io.BytesIO()
    pd.DataFrame({"x": [1], "y": [2]}).to_excel(plano, index=False)
    assert leer_auxiliar_world_office(plano.getvalue()) is None


def pdf_extracto(saldo_final="1,300.00", abonos="500.00"):
    html = f"""<html><body style="font-family:monospace"><p>ESTADO DE CUENTA</p><p>DESDE: 2026/08/31 HASTA: 2026/09/30</p>
    <p>SALDO ANTERIOR $ 1,000.00</p><p>TOTAL ABONOS $ {abonos}</p><p>TOTAL CARGOS $ 200.00</p><p>SALDO ACTUAL $ 1,300.00</p>
    <table style="width:100%"><tr><td>1/09</td><td>PAGO UNO</td><td>-200.00</td><td>800.00</td></tr>
    <tr><td>2/09</td><td>ABONO DOS</td><td>500.00</td><td>{saldo_final}</td></tr></table></body></html>"""
    return HTML(string=html).write_pdf()


def test_extracto_pdf_toma_el_anio_del_rango_y_cuadra():
    lec = leer_extracto_bancolombia_pdf(pdf_extracto())
    assert not lec.bloqueos
    assert [(f["fecha"], f["valor"]) for f in lec.filas] == [(date(2026, 9, 1), D("-200.00")), (date(2026, 9, 2), D("500.00"))]
    assert lec.info["totales_cuadran"] and lec.info["saldo_final"] == "1300.00"


def test_extracto_pdf_con_saldo_roto_o_resumen_distinto_bloquea():
    assert leer_extracto_bancolombia_pdf(pdf_extracto(saldo_final="1,299.00")).bloqueos
    assert leer_extracto_bancolombia_pdf(pdf_extracto(abonos="400.00")).bloqueos


def test_extracto_pdf_ajeno_devuelve_none():
    assert leer_extracto_bancolombia_pdf(HTML(string="<p>Hola</p>").write_pdf()) is None
    assert leer_extracto_bancolombia_pdf(b"no es un pdf") is None


def test_leer_enruta_pdf_y_auxiliar_jerarquico():
    assert importacion.leer(pdf_extracto(), "extracto.pdf", "extracto_banco", None).info["formato"].startswith("extracto")
    assert importacion.leer(auxiliar(), "aux.xlsx", "auxiliar", None).info["formato"].startswith("libro auxiliar")


@pytest.mark.django_db
def test_formulario_rechaza_perfil_de_otro_tipo():
    perfil = PerfilImportacion.objects.create(nombre="DIAN", tipo="facturas_dian", mapeo={"numero": "Folio"})
    datos = {"tipo": "balance", "anio": 2026, "mes": 10, "perfil": perfil.pk}
    form = CargaForm(datos, {"archivo": SimpleUploadedFile("b.xlsx", b"x")})
    assert not form.is_valid() and "perfil" in form.errors
    form = CargaForm({**datos, "tipo": "facturas_dian", "sentido": "emitida"}, {"archivo": SimpleUploadedFile("b.xlsx", b"x")})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_desplegable_de_perfil_marca_cada_opcion_con_su_tipo():
    PerfilImportacion.objects.create(nombre="DIAN", tipo="facturas_dian")
    assert 'data-tipo="facturas_dian"' in str(CargaForm()["perfil"])
