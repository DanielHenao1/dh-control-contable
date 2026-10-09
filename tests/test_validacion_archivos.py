import io

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from empresa.models import ArchivoCargado, Empresa, PerfilImportacion, Periodo, RegistroAuditoria
from empresa.validacion_archivos import verificar

from .conftest import usuario_con_rol


def xlsx(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def pdf(texto):
    from weasyprint import HTML

    return HTML(string=f"<html><body><p>{texto}</p></body></html>").write_pdf()


@pytest.fixture
def empresa(datos_iniciales):
    return Empresa.actual()


@pytest.fixture
def septiembre(db):
    return Periodo.obtener(2026, 9)


BALANCE = pd.DataFrame({"Cuenta": ["1105"], "Débito": [10], "Crédito": [5], "Saldo final": [5]})


def facturas(nit_emisor, nit_receptor, fecha="2026-09-10"):
    return pd.DataFrame({
        "Número": ["F1", "F2"], "Fecha": [fecha, fecha], "NIT emisor": [nit_emisor] * 2, "NIT receptor": [nit_receptor] * 2, "Total": [100, 200],
    })


def test_extension_incorrecta(empresa, septiembre):
    r = verificar("balance", "balance.pdf", b"%PDF", septiembre, empresa)
    assert not r.ok and "debe ser" in r.errores[0]


def test_balance_correcto_sin_errores(empresa, septiembre):
    assert verificar("balance", "b.xlsx", xlsx(BALANCE), septiembre, empresa).ok


def test_balance_subido_como_auxiliar_avisa_del_tipo(empresa, septiembre):
    r = verificar("auxiliar", "b.xlsx", xlsx(BALANCE), septiembre, empresa)
    assert not r.ok and "parece un balance de prueba" in r.errores[0]


def test_columnas_desconocidas_solo_avisan(empresa, septiembre):
    r = verificar("balance", "x.xlsx", xlsx(pd.DataFrame({"A": [1], "B": [2]})), septiembre, empresa)
    assert r.ok and "mapearlas a mano" in r.avisos[0]


def test_archivo_vacio_o_danado(empresa, septiembre):
    assert not verificar("balance", "x.xlsx", b"no es excel", septiembre, empresa).ok
    assert not verificar("balance", "x.xlsx", xlsx(pd.DataFrame({"Cuenta": [], "Débito": [], "Crédito": [], "Saldo final": []})), septiembre, empresa).ok


def test_facturas_de_otra_empresa(empresa, septiembre):
    r = verificar("facturas_dian", "f.xlsx", xlsx(facturas("111222333", "444555666")), septiembre, empresa, sentido="recibida")
    assert not r.ok and "otra empresa" in r.errores[0]


def test_facturas_sentido_equivocado_y_correcto(empresa, septiembre):
    recibidas = xlsx(facturas("111222333", empresa.nit))
    assert verificar("facturas_dian", "f.xlsx", recibidas, septiembre, empresa, sentido="recibida").ok
    r = verificar("facturas_dian", "f.xlsx", recibidas, septiembre, empresa, sentido="emitida")
    assert not r.ok and "recibidas (compras)" in r.errores[0]


def test_fechas_de_otro_periodo_avisan(empresa, septiembre):
    r = verificar("facturas_dian", "f.xlsx", xlsx(facturas("111222333", empresa.nit, fecha="2026-03-10")), septiembre, empresa, sentido="recibida")
    assert r.ok and "no son de 09/2026" in r.avisos[0]


def test_declaracion_formulario_correcto_y_equivocado(empresa, septiembre):
    f350 = pdf(f"Formulario 350 Declaración mensual de retención en la fuente NIT {empresa.nit} periodo septiembre 2026 " + "texto " * 20)
    assert verificar("declaracion", "d.pdf", f350, septiembre, empresa, formulario="350").ok
    r = verificar("declaracion", "d.pdf", f350, septiembre, empresa, formulario="300")
    assert not r.ok and "Formulario 350" in r.errores[0]
    f300 = pdf(f"Formulario 300 Declaración del impuesto sobre las ventas IVA NIT {empresa.nit} " + "texto " * 20)
    assert verificar("declaracion", "d.pdf", f300, septiembre, empresa, formulario="300").ok
    assert not verificar("declaracion", "d.pdf", f300, septiembre, empresa, formulario="350").ok


def test_declaracion_de_otro_nit_o_escaneada_avisa(empresa, septiembre):
    otro = pdf("Formulario 350 Declaración de retención en la fuente NIT 800100200 " + "texto " * 20)
    r = verificar("declaracion", "d.pdf", otro, septiembre, empresa, formulario="350")
    assert r.ok and any("NIT" in a for a in r.avisos)
    vacio = pdf("x")
    r = verificar("declaracion", "d.pdf", vacio, septiembre, empresa, formulario="350")
    assert r.ok and "escaneado" in r.avisos[0]
    assert not verificar("declaracion", "d.pdf", b"no es pdf", septiembre, empresa, formulario="350").ok


def _subir(cliente, contenido, nombre, **extra):
    datos = {"tipo": "auxiliar", "anio": 2026, "mes": 9, "archivo": SimpleUploadedFile(nombre, contenido), **extra}
    return cliente.post("/cargas/nueva/", datos)


def test_vista_bloquea_y_el_dueno_puede_forzar(cliente_dueno, empresa):
    r = _subir(cliente_dueno, xlsx(BALANCE), "b.xlsx")
    assert r.status_code == 200 and "parece un balance de prueba" in r.content.decode()
    assert not ArchivoCargado.objects.exists()
    r = _subir(cliente_dueno, xlsx(BALANCE), "b.xlsx", subir_igual="on")
    assert r.status_code == 302
    a = ArchivoCargado.objects.get()
    assert a.verificaciones["errores_ignorados"]
    assert RegistroAuditoria.objects.filter(accion="carga_forzada").exists()


def test_el_asistente_no_puede_forzar(datos_iniciales):
    c = Client()
    c.force_login(usuario_con_rol("asistente"))
    r = _subir(c, xlsx(BALANCE), "b.xlsx", subir_igual="on")
    assert r.status_code == 200 and not ArchivoCargado.objects.exists()
    assert "Subir de todas formas" not in r.content.decode()


def test_vista_guarda_avisos_y_exige_formulario(cliente_dueno, empresa):
    r = _subir(cliente_dueno, xlsx(pd.DataFrame({"A": [1], "B": [2]})), "x.xlsx", tipo="balance")
    assert r.status_code == 302
    assert "mapearlas a mano" in ArchivoCargado.objects.get().verificaciones["avisos"][0]
    r = _subir(cliente_dueno, pdf("Formulario 350"), "d.pdf", tipo="declaracion")
    assert r.status_code == 200 and "Elige qué formulario" in r.content.decode()



def _facturas_meses(empresa, sentido="recibida", meses=(1, 2, 9), numero_base=100):
    filas = []
    for i, m in enumerate(meses):
        filas.append({
            "Número": f"F{numero_base + i}", "Fecha": f"2026-{m:02d}-10",
            "NIT emisor": "800100100" if sentido == "recibida" else empresa.nit,
            "NIT receptor": empresa.nit if sentido == "recibida" else "900300300", "Total": 1190 * (i + 1), "IVA": 190 * (i + 1),
        })
    return xlsx(pd.DataFrame(filas))


def _subir_y_confirmar(cliente, contenido, nombre, mes=9, **extra):
    from django.core.files.uploadedfile import SimpleUploadedFile

    r = cliente.post("/cargas/nueva/", {"tipo": "facturas_dian", "anio": 2026, "mes": mes, "sentido": "recibida",
                                        "archivo": SimpleUploadedFile(nombre, contenido), **extra})
    assert r.status_code == 302, r.content.decode()[:600]
    pk = int(r.url.rstrip("/").split("/")[-1])
    cliente.post(f"/cargas/{pk}/confirmar/")
    return ArchivoCargado.objects.get(pk=pk)


def test_varios_meses_reparte_las_facturas_por_su_fecha(cliente_dueno, empresa):
    from facturacion.models import Factura

    a = _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa), "enero_a_septiembre.xlsx", varios_meses="on")
    assert a.estado == "importado" and a.varios_meses and a.resumen["meses"] == ["2026-01", "2026-02", "2026-09"]
    assert {(f.periodo.anio, f.periodo.mes) for f in Factura.objects.all()} == {(2026, 1), (2026, 2), (2026, 9)}


def test_sin_varios_meses_avisa_de_las_fechas_de_otro_periodo(cliente_dueno, empresa):
    from django.core.files.uploadedfile import SimpleUploadedFile

    r = cliente_dueno.post("/cargas/nueva/", {"tipo": "facturas_dian", "anio": 2026, "mes": 9, "sentido": "recibida",
                                              "archivo": SimpleUploadedFile("x.xlsx", _facturas_meses(empresa))})
    assert r.status_code == 302
    assert "no son de 09/2026" in ArchivoCargado.objects.get().verificaciones["avisos"][0]


def test_varios_meses_en_mes_cerrado_no_importa(cliente_dueno, empresa):
    from facturacion.models import Factura

    p = Periodo.obtener(2026, 2)
    p.estado = "cerrado"
    p.save()
    a = _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa), "x.xlsx", varios_meses="on")
    assert a.estado != "importado" and not Factura.objects.exists()


def test_no_se_duplican_meses_entre_archivos(cliente_dueno, empresa):
    from facturacion.models import Factura

    _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa), "grande.xlsx", varios_meses="on")
    # Un archivo mensual de septiembre ya cubierto por el de varios meses: no se confirma
    mensual = _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa, meses=(9,), numero_base=500), "sep.xlsx")
    assert mensual.estado != "importado"
    assert Factura.objects.count() == 3
    # Otro archivo de varios meses (con otro periodo final) que repita enero: tampoco
    otro = _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa, meses=(1, 3), numero_base=700), "otro.xlsx", mes=6, varios_meses="on")
    assert otro.estado != "importado" and Factura.objects.count() == 3


def test_un_archivo_de_varios_meses_reemplaza_al_anterior_del_mismo_grupo(cliente_dueno, empresa):
    from facturacion.models import facturas_vigentes

    _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa), "v1.xlsx", varios_meses="on")
    _subir_y_confirmar(cliente_dueno, _facturas_meses(empresa, meses=(1, 2, 3, 9), numero_base=900), "v2.xlsx", varios_meses="on")
    assert facturas_vigentes().count() == 4  # solo las del archivo nuevo


def test_varios_meses_solo_para_facturas(cliente_dueno, empresa):
    from django.core.files.uploadedfile import SimpleUploadedFile

    r = cliente_dueno.post("/cargas/nueva/", {"tipo": "balance", "anio": 2026, "mes": 9, "varios_meses": "on",
                                              "archivo": SimpleUploadedFile("b.xlsx", xlsx(BALANCE))})
    assert r.status_code == 200 and "solo aplica a facturas" in r.content.decode()


COLUMNAS_DIAN = [
    "Tipo de documento", "CUFE/CUDE", "Folio", "Prefijo", "Divisa", "Fecha Emisión", "NIT Emisor", "Nombre Emisor",
    "NIT Receptor", "Nombre Receptor", "IVA", "Total", "Estado", "Grupo",
]


def _fila_dian(tipo, folio, fecha, emisor, receptor, iva, total, grupo):
    return [tipo, f"CUFE{folio}{grupo}", folio, "FE", "COP", fecha, emisor, "EMISOR EJEMPLO", receptor, "RECEPTOR EJEMPLO",
            iva, total, "Aprobado", grupo]


def libro_dian(empresa, sin_encabezado_en=None):
    """Libro como el que baja la DIAN: una hoja por mes, columna Grupo y documentos que no son facturas."""
    buf = io.BytesIO()
    nit = int(empresa.nit)
    with pd.ExcelWriter(buf) as w:
        for mes, hoja in ((1, "ENERO"), (2, "FEBRERO "), (3, "MARZO")):
            filas = [
                _fila_dian("Factura electrónica", 100 + mes, f"10-{mes:02d}-2026", nit, 900300300, 190, 1190, "Emitido"),
                _fila_dian("Factura electrónica", 200 + mes, f"12-{mes:02d}-2026", 800100100, nit, 380, 2380, "Recibido"),
                _fila_dian("Documento soporte con no obligados", 300 + mes, f"15-{mes:02d}-2026", nit, 35511082, 0, 650000, "Emitido"),
                _fila_dian("Application response", 400 + mes, f"12-{mes:02d}-2026", 800100100, nit, 0, 0, "Recibido"),
                _fila_dian("Nomina Individual", 500 + mes, f"28-{mes:02d}-2026", nit, 53062507, 0, 1500000, "Emitido"),
            ]
            df = pd.DataFrame(filas, columns=COLUMNAS_DIAN)
            if hoja.strip() == sin_encabezado_en:
                df.to_excel(w, sheet_name=hoja, index=False, header=False, startrow=1)  # primera fila vacía y sin encabezado
            else:
                df.to_excel(w, sheet_name=hoja, index=False)
    return buf.getvalue()


def test_libro_de_la_dian_con_una_hoja_por_mes(cliente_dueno, empresa):
    from facturacion.models import Factura

    perfil = PerfilImportacion.objects.get(tipo="facturas_dian")
    a = _subir_y_confirmar(cliente_dueno, libro_dian(empresa, sin_encabezado_en="FEBRERO"), "dian.xlsx",
                           perfil=perfil.pk, varios_meses="on", sentido="")
    assert a.estado == "importado", a.errores
    assert a.resumen["facturas"] == 9 and a.resumen["no_son_facturas_omitidas"] == 6
    assert a.resumen["meses"] == ["2026-01", "2026-02", "2026-03"]
    assert Factura.objects.filter(sentido="emitida", tipo_documento="factura").count() == 3
    assert Factura.objects.filter(sentido="recibida", tipo_documento="factura").count() == 3
    assert Factura.objects.filter(sentido="emitida", tipo_documento="doc_soporte").count() == 3
    assert {(f.periodo.anio, f.periodo.mes) for f in Factura.objects.all()} == {(2026, 1), (2026, 2), (2026, 3)}


def test_libro_sin_ningun_encabezado_se_rechaza_con_un_mensaje(cliente_dueno, empresa):
    from django.core.files.uploadedfile import SimpleUploadedFile

    buf = io.BytesIO()
    pd.DataFrame([_fila_dian("Factura electrónica", 1, "10-01-2026", 1, 2, 0, 5, "Emitido")]).to_excel(buf, index=False, header=False)
    r = cliente_dueno.post("/cargas/nueva/", {
        "tipo": "facturas_dian", "anio": 2026, "mes": 9, "varios_meses": "on",
        "perfil": PerfilImportacion.objects.get(tipo="facturas_dian").pk,
        "archivo": SimpleUploadedFile("x.xlsx", buf.getvalue())})
    assert r.status_code == 200 and "no tiene encabezado" in r.content.decode()


def test_sentido_obligatorio_salvo_que_el_perfil_lo_mapee(cliente_dueno, empresa):
    from django.core.files.uploadedfile import SimpleUploadedFile

    PerfilImportacion.objects.filter(tipo="facturas_dian").update(activo=False)  # sin perfil DIAN, el sentido es obligatorio
    r = cliente_dueno.post("/cargas/nueva/", {"tipo": "facturas_dian", "anio": 2026, "mes": 9,
                                              "archivo": SimpleUploadedFile("x.csv", b"a\n1\n")})
    assert r.status_code == 200 and "emitidas o recibidas" in r.content.decode()


def test_columna_grupo_incoherente_con_los_nit(cliente_dueno, empresa):
    perfil = PerfilImportacion.objects.get(tipo="facturas_dian")
    buf = io.BytesIO()
    nit = int(empresa.nit)
    filas = [_fila_dian("Factura electrónica", i, "10-09-2026", 800100100, nit, 190, 1190, "Emitido") for i in range(1, 5)]
    pd.DataFrame(filas, columns=COLUMNAS_DIAN).to_excel(buf, index=False)
    r = verificar("facturas_dian", "x.xlsx", buf.getvalue(), Periodo.obtener(2026, 9), Empresa.actual(), perfil)
    assert r.ok and "no coinciden con su columna Emitido/Recibido" in r.avisos[0]
    otra = pd.DataFrame([_fila_dian("Factura electrónica", 1, "10-09-2026", 1, 2, 0, 5, "Emitido")], columns=COLUMNAS_DIAN)
    buf2 = io.BytesIO()
    otra.to_excel(buf2, index=False)
    r = verificar("facturas_dian", "x.xlsx", buf2.getvalue(), Periodo.obtener(2026, 9), Empresa.actual(), perfil)
    assert not r.ok and "otra empresa" in r.errores[0]
