"""Balance de prueba jerárquico de World Office (con terceros), mapeo con otra fila de encabezado y borrado de cargas."""
import io
from decimal import Decimal

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from contabilidad.models import Cuenta, SaldoCuenta
from empresa import importacion
from empresa.models import ArchivoCargado, Periodo, RegistroAuditoria

from .conftest import usuario_con_rol

D = Decimal


def fmt(valor):
    """Formato colombiano del exporte: 1.454.134,91; negativos entre paréntesis; cero como «-»."""
    v = D(str(valor))
    if v == 0:
        return "-"
    texto = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"({texto})" if v < 0 else texto


# (código, nombre, [(tercero, saldo inicial, débitos, créditos, saldo final)])
HOJAS = [
    ("11050501", "CAJA GENERAL", [("CAJA GENERAL", "1454134.91", "3749000", "3740692.99", "1462441.92")]),
    ("110510", "CAJAS MENORES", [("DH TRANS STORAGE SAS", "51999", "0", "0", "51999"),
                                 ("PINEDA SASTOQUE MARIA PATRICIA", "-51999", "0", "0", "-51999")]),
    ("11100501", "Bco. Bancolombia Cta. Corriente No.63462550891",
     [("Bco. Bancolombia Cta. Corriente No.63462550891", "46618399.92", "168524281", "179950103.42", "35192577.50")]),
    ("11200501", "MERCADOPAGO", [("MERCADOPAGO", "-7487083.49", "3927700", "5971433.65", "-9530817.14")]),
    ("22050101", "PROVEEDORES", [("TOTAL ENERGIES SAS", "0", "1000", "9000", "8000"), ("OTRO PROVEEDOR SAS", "0", "500", "700", "200")]),
]


def construir(hojas=HOJAS, desfase=0, alterar_total_clase=None, texto=True, con_huerfana=False):
    """Hoja como la que exporta World Office: títulos, encabezado y jerarquía con agrupaciones, detalle y totales."""
    celdas = [[None] * 5 for _ in range(5 + desfase)]
    celdas[0][0], celdas[1][0] = "DH TRANS STORAGE SAS", "NIT 900902549-7"
    celdas[2][0] = "Balance de Prueba entre el 01/09/2026 y el 30/09/2026"
    celdas[3][0] = "Elaborado Bajo Normas Locales"
    celdas.append([None, "Saldo Inicial", "Débitos", "Créditos", "Saldo Final"])
    f = (lambda v: fmt(v)) if texto else (lambda v: float(v))
    if con_huerfana:
        celdas.append(["DETALLE SIN AGRUPACION", f(10), f(5), f(5), f(10)])
    por_clase = {}
    for codigo, nombre, detalle in hojas:
        celdas.append([f"{codigo[0]} CLASE", None, None, None, None]) if codigo[0] not in por_clase else None
        celdas.append([f"{codigo} {nombre}", None, None, None, None])
        suma = [D(0)] * 4
        for tercero, *vals in detalle:
            celdas.append([tercero, *[f(v) for v in vals]])
            suma = [a + D(b) for a, b in zip(suma, vals, strict=True)]
        celdas.append([f"Total {codigo} {nombre}", *[f(v) for v in suma]])
        acumulado = por_clase.setdefault(codigo[0], [D(0)] * 4)
        por_clase[codigo[0]] = [a + b for a, b in zip(acumulado, suma, strict=True)]
    for clase, suma in por_clase.items():
        if alterar_total_clase == clase:
            suma = [suma[0], suma[1] + D(5000), *suma[2:]]  # débitos de la clase
        celdas.append([f"Total {clase} CLASE", *[f(v) for v in suma]])
    buf = io.BytesIO()
    pd.DataFrame(celdas).to_excel(buf, index=False, header=False)
    return buf.getvalue()


def _subir(cliente, contenido, tipo="balance", **extra):
    r = cliente.post("/cargas/nueva/", {"tipo": tipo, "anio": 2026, "mes": 9,
                                        "archivo": SimpleUploadedFile("BALNCE DE PRUEBA CON TERCEROS.xlsx", contenido), **extra})
    assert r.status_code == 302, r.content.decode()[:500]
    pk = int(r.url.rstrip("/").split("/")[-1])
    return ArchivoCargado.objects.get(pk=pk)


def test_numeros_con_formato_colombiano():
    p = importacion.parse_numero_colombiano
    assert p("1.454.134,91") == D("1454134.91") and p("(51.999,00)") == D("-51999.00")
    assert p("-") == D("0") and p(None) is None and p("") is None and p(1234.5) == D("1234.5")
    assert p("51.999") == D("51999") and p("12,5") == D("12.5") and p("-1.200,00") == D("-1200.00")
    with pytest.raises(ValueError):
        p("abc")


def test_importa_solo_el_detalle_con_el_codigo_de_su_agrupacion(cliente_dueno, db):
    a = _subir(cliente_dueno, construir())
    cliente_dueno.post(f"/cargas/{a.pk}/confirmar/")
    a.refresh_from_db()
    assert a.estado == "importado", a.errores
    assert a.resumen["totales_cuadran"] is True and a.resumen["filas_importadas"] == 7
    assert a.resumen["ignoradas_detalle"]["totales"] == 7  # 5 subtotales + 2 totales de clase
    assert a.resumen["ignoradas_detalle"]["agrupaciones"] == 7  # 5 cuentas + 2 clases
    codigos = set(SaldoCuenta.objects.filter(archivo=a).values_list("cuenta__codigo", flat=True))
    assert codigos == {"11050501", "110510", "11100501", "11200501", "22050101"}
    assert not Cuenta.objects.filter(nombre__startswith="Total").exists()
    # Varios terceros de la misma cuenta se suman en una sola fila de saldo
    menores = SaldoCuenta.objects.get(archivo=a, cuenta__codigo="110510")
    assert menores.saldo_inicial == 0 and menores.saldo_final == 0
    prov = SaldoCuenta.objects.get(archivo=a, cuenta__codigo="22050101")
    assert (prov.debito, prov.credito, prov.saldo_final) == (D("1500"), D("9700"), D("8200"))
    assert SaldoCuenta.objects.get(archivo=a, cuenta__codigo="11200501").saldo_final == D("-9530817.14")
    assert Cuenta.objects.get(codigo="11100501").nombre.startswith("Bco. Bancolombia")


def test_funciona_con_celdas_numericas_y_con_otro_numero_de_filas_de_titulo(cliente_dueno, db):
    a = _subir(cliente_dueno, construir(desfase=3, texto=False))
    cliente_dueno.post(f"/cargas/{a.pk}/confirmar/")
    a.refresh_from_db()
    assert a.estado == "importado" and a.resumen["totales_cuadran"] is True


def test_un_tercero_que_empieza_por_total_es_detalle(cliente_dueno, db):
    a = _subir(cliente_dueno, construir())
    lectura = importacion.leer_balance_world_office(a.archivo.read())
    assert "TOTAL ENERGIES SAS" in {f["tercero"] for f in lectura.filas}


def test_totales_que_no_cuadran_marcan_error_y_explican_la_diferencia(cliente_dueno, db):
    a = _subir(cliente_dueno, construir(alterar_total_clase="1"))
    cliente_dueno.post(f"/cargas/{a.pk}/confirmar/", {"omitir": "on"})  # omitir filas no salta este control
    a.refresh_from_db()
    assert a.estado == "error" and not SaldoCuenta.objects.exists()
    mensaje = a.errores[0]["problemas"][0]
    assert "no cuadran" in mensaje and "clase 1" in mensaje


def test_fila_con_cifras_sin_agrupacion_se_ignora_con_aviso(cliente_dueno, db):
    lectura = importacion.leer_balance_world_office(construir(con_huerfana=True))
    assert lectura.info["ignoradas_detalle"]["sin_agrupacion"] == 1
    assert any("sin agrupación" in a or "no tienen una agrupación" in a for a in lectura.avisos)
    assert "DETALLE SIN AGRUPACION" not in {f["tercero"] for f in lectura.filas}


def test_un_balance_plano_sigue_leyendose_como_antes():
    plano = io.BytesIO()
    pd.DataFrame({"cuenta": ["1105"], "debito": [10], "credito": [0], "saldo_final": [10]}).to_excel(plano, index=False)
    assert importacion.leer_balance_world_office(plano.getvalue()) is None
    assert importacion.leer(plano.getvalue(), "b.xlsx", "balance", None).filas[0]["cuenta"] == "1105"


def test_detecta_la_fila_del_encabezado():
    assert importacion.detectar_fila_encabezado(construir(), "b.xlsx") == 6
    assert importacion.detectar_fila_encabezado(construir(desfase=2), "b.xlsx") == 8


def test_mapeo_recalcula_las_columnas_con_otra_fila(cliente_dueno, db):
    a = _subir(cliente_dueno, construir(), tipo="auxiliar")  # sin lector propio: se mapea a mano
    r1 = cliente_dueno.get(f"/cargas/{a.pk}/columnas/?fila=1").json()
    r6 = cliente_dueno.get(f"/cargas/{a.pk}/columnas/?fila=6").json()
    assert "DH TRANS STORAGE SAS" in r1["columnas"] and "Saldo Inicial" not in r1["columnas"]
    assert {"Saldo Inicial", "Débitos", "Créditos", "Saldo Final"} <= set(r6["columnas"])
    assert cliente_dueno.get(f"/cargas/{a.pk}/columnas/?fila=500").status_code in (200, 400)
    html = cliente_dueno.get(f"/cargas/{a.pk}/mapear/").content.decode()
    assert 'value="6"' in html  # propone la fila de encabezado detectada


def test_borrar_una_carga_importada_borra_sus_datos_y_deja_auditoria(cliente_dueno, db):
    a = _subir(cliente_dueno, construir())
    cliente_dueno.post(f"/cargas/{a.pk}/confirmar/")
    a.refresh_from_db()
    assert a.vigente and SaldoCuenta.objects.exists()
    # sin la casilla no se borra
    cliente_dueno.post(f"/cargas/{a.pk}/eliminar/")
    assert ArchivoCargado.objects.filter(pk=a.pk).exists()
    r = cliente_dueno.post(f"/cargas/{a.pk}/eliminar/", {"entiendo": "on"})
    assert r.status_code == 302
    assert not ArchivoCargado.objects.exists() and not SaldoCuenta.objects.exists()
    registro = RegistroAuditoria.objects.get(accion="eliminar_carga")
    assert registro.detalle["hash"] == a.hash_sha256 and registro.detalle["filas_borradas"]["SaldoCuenta"] == 5
    # y el mismo archivo se puede volver a subir
    assert _subir(cliente_dueno, construir()).pk


def test_borrar_promueve_la_carga_anterior_como_vigente(cliente_dueno, db):
    primera = _subir(cliente_dueno, construir())
    cliente_dueno.post(f"/cargas/{primera.pk}/confirmar/")
    segunda = _subir(cliente_dueno, construir(alterar_total_clase=None, hojas=HOJAS[:4]))
    cliente_dueno.post(f"/cargas/{segunda.pk}/confirmar/")
    primera.refresh_from_db()
    assert not primera.vigente
    cliente_dueno.post(f"/cargas/{segunda.pk}/eliminar/", {"entiendo": "on"})
    primera.refresh_from_db()
    assert primera.vigente


def test_no_se_borra_en_un_mes_cerrado_ni_sin_permiso(cliente_dueno, db):
    a = _subir(cliente_dueno, construir())
    cliente_dueno.post(f"/cargas/{a.pk}/confirmar/")
    asistente = Client()
    asistente.force_login(usuario_con_rol("asistente"))
    assert asistente.post(f"/cargas/{a.pk}/eliminar/", {"entiendo": "on"}).status_code == 403
    p = Periodo.obtener(2026, 9)
    p.estado = "cerrado"
    p.save()
    cliente_dueno.post(f"/cargas/{a.pk}/eliminar/", {"entiendo": "on"})
    assert ArchivoCargado.objects.filter(pk=a.pk).exists() and SaldoCuenta.objects.exists()
