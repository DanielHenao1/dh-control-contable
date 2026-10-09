import io
from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook

from asistente.servicio import explicacion_local, explicar, minimizar
from conciliaciones import servicios
from conciliaciones.models import MovimientoBanco
from controles.models import Hallazgo, ReglaControl
from empresa.models import Empresa, Parametro
from reportes.informe import generar_excel, generar_pdf

from .helpers import archivo, auxiliar, balance, factura, periodo


@pytest.mark.django_db
def test_conciliar_banco(datos_iniciales):
    p = periodo()
    auxiliar(p, [
        (date(2026, 9, 1), "R1", "", "111005", "", 1000, 0),
        (date(2026, 9, 5), "E1", "", "111005", "", 0, 300),
        (date(2026, 9, 9), "E2", "", "111005", "", 0, 50),
    ])
    a = archivo("extracto_banco", p)
    for f, v in ((date(2026, 9, 2), 1000), (date(2026, 9, 5), -300), (date(2026, 9, 20), -77)):
        MovimientoBanco.objects.create(periodo=p, archivo=a, fecha=f, valor=Decimal(v))
    r = servicios.conciliar_banco(p, "1110")
    assert r["conciliadas"] == 2 and len(r["solo_banco"]) == 1 and len(r["solo_libros"]) == 1


@pytest.mark.django_db
def test_conciliar_facturas_y_terceros(datos_iniciales):
    p = periodo()
    factura(p, "recibida", "1", date(2026, 9, 5), "900111", "900902549", 1000, 190, prefijo="F")
    factura(p, "recibida", "2", date(2026, 9, 6), "900111", "900902549", 1000, 190, prefijo="F")
    auxiliar(p, [(date(2026, 9, 5), "C1", "F1", "220505", "900111", 0, 1190), (date(2026, 9, 5), "C1", "F1", "513595", "900111", 1190, 0)])
    r = servicios.conciliar_facturas(p)
    compras = r["filas"][1]
    assert compras["facturas"] == 2 and compras["causadas"] == 1 and compras["sin_causar"] == 1
    t = servicios.conciliar_terceros(p, ["22"], -1)
    assert t["total"] == Decimal("1190")
    assert servicios.conciliar_auxiliares_vs_balance(p)["filas"]


@pytest.mark.django_db
def test_informe_excel_y_pdf(datos_iniciales):
    p = periodo()
    balance(p, [("1105", "Caja", 0, 0, 0, -10)])
    from controles.motor import ejecutar_reglas

    ejecutar_reglas(p)
    wb = load_workbook(io.BytesIO(generar_excel(p)))
    assert wb.sheetnames == ["Resumen", "Hallazgos", "Vencimientos"]
    assert wb["Hallazgos"].max_row > 1
    contenido, tipo = generar_pdf(p)
    assert contenido and tipo in ("application/pdf", "text/html; charset=utf-8")
    if tipo == "application/pdf":
        assert contenido.startswith(b"%PDF")


@pytest.mark.django_db
def test_descarga_informe_por_http(cliente_dueno, datos_iniciales):
    r = cliente_dueno.get("/informes/excel/?anio=2026&mes=9")
    assert r.status_code == 200 and r["Content-Type"].endswith("sheet")
    r = cliente_dueno.get("/informes/pdf/?anio=2026&mes=9")
    assert r.status_code == 200


def test_minimizar_quita_identificadores():
    t = minimizar("NIT 900.902.549-7, cédula 1020304050, correo juan@empresa.com, valor 1.500")
    assert "900.902.549" not in t and "1020304050" not in t and "juan@" not in t and "1.500" in t


@pytest.mark.django_db
def test_asistente_sin_clave_usa_plantilla(datos_iniciales, settings):
    from controles.motor import sincronizar_catalogo

    sincronizar_catalogo()
    h = Hallazgo.objects.create(regla=ReglaControl.objects.get(codigo="INT001"), periodo=periodo(), clave="x",
                                titulo="Débitos distintos de créditos", detalle="Diferencia 10", severidad="alta")
    settings.ANTHROPIC_API_KEY = ""
    e = explicar(h)
    assert e.modelo == "local" and "Diferencia 10" in e.texto
    assert "contador" in explicacion_local(h)


@pytest.mark.django_db
def test_asistente_con_api_envia_solo_datos_minimos(datos_iniciales, settings, monkeypatch):
    from asistente import servicio
    from controles.motor import sincronizar_catalogo

    sincronizar_catalogo()
    h = Hallazgo.objects.create(regla=ReglaControl.objects.get(codigo="TER001"), periodo=periodo(), clave="x",
                                titulo="DV errado para 900.902.549-7", detalle="juan@x.com", severidad="media")
    settings.ANTHROPIC_API_KEY = "clave-de-prueba"
    enviado = {}

    def falso(payload):
        enviado.update(payload)
        return {"content": [{"type": "text", "text": "Explicación redactada."}]}

    monkeypatch.setattr(servicio, "_llamar_api", falso)
    e = explicar(h)
    assert e.texto == "Explicación redactada."
    cuerpo = enviado["messages"][0]["content"]
    assert "900.902.549" not in cuerpo and "juan@x.com" not in cuerpo
    assert "NO calcules" in enviado["system"]


@pytest.mark.django_db
def test_flujo_http_de_carga_y_hallazgos(cliente_dueno, datos_iniciales):
    csv = b"cuenta,debito,credito,saldo_final\n1105,100,0,100\n2205,0,90,90\n"
    r = cliente_dueno.post("/cargas/nueva/", {"tipo": "balance", "anio": 2026, "mes": 9, "archivo": SimpleUploadedFile("b.csv", csv)})
    assert r.status_code == 302
    detalle = cliente_dueno.get(r.url)
    assert detalle.status_code == 200 and b"Vista previa" in detalle.content
    r2 = cliente_dueno.post(r.url + "confirmar/")
    assert r2.status_code == 302
    h = cliente_dueno.get("/hallazgos/?anio=2026&mes=9")
    assert b"d\xc3\xa9bitos no son iguales" in h.content.lower() or b"INT001" in h.content
    hallazgo = Hallazgo.objects.filter(regla__codigo="INT001").first()
    r3 = cliente_dueno.post(f"/hallazgos/{hallazgo.pk}/", {"accion": "estado", "estado": "explicado", "explicacion": "Ajuste pendiente de Ideako"})
    hallazgo.refresh_from_db()
    assert hallazgo.estado == "explicado" and r3.status_code == 302
    sin = cliente_dueno.post(f"/hallazgos/{hallazgo.pk}/", {"accion": "estado", "estado": "explicado", "explicacion": ""})
    assert sin.status_code == 302


@pytest.mark.django_db
def test_tablero_con_datos(cliente_dueno, datos_iniciales):
    p = periodo()
    balance(p, [("4135", "Ventas", 0, 0, 500, 500), ("1105", "Caja", 0, 500, 0, 500)])
    r = cliente_dueno.get("/?anio=2026&mes=9")
    assert r.status_code == 200 and b"Ingresos acumulados" in r.content
    assert Empresa.actual().nit_formateado == "900.902.549-7"
    Parametro.objects.filter(codigo="RENTA_TARIFA").delete()
    assert cliente_dueno.get("/fiscal/?anio=2026&mes=9").status_code == 200
