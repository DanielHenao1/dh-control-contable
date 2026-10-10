import io
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from contabilidad.models import Cuenta, Movimiento, SaldoCuenta
from empresa import cargas
from empresa.importacion import leer, parse_fecha, parse_numero, sugerir_mapeo
from empresa.models import ArchivoCargado, PerfilImportacion, Periodo, PeriodoCerrado
from terceros.models import Tercero


def xlsx(df):
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    return buf.getvalue()


def test_numeros_y_fechas():
    assert parse_numero("1.234.567,89", decimal_coma=True) == Decimal("1234567.89")
    assert parse_numero("1,234,567.89") == Decimal("1234567.89")
    assert parse_numero("(1,000)") == Decimal("-1000")
    assert parse_numero("500-") == Decimal("-500")
    assert parse_numero(None) == Decimal("0")
    assert parse_fecha("2026-09-30") == date(2026, 9, 30)
    assert parse_fecha("30/09/2026") == date(2026, 9, 30)
    with pytest.raises(ValueError):
        parse_numero("abc")


def test_mapeo_sugerido_y_perfil():
    df = pd.DataFrame({"Cuenta": ["1105"], "Débito": [10], "Credito": [5]})
    assert sugerir_mapeo("balance", list(df.columns)) == {"cuenta": "Cuenta", "debito": "Débito", "credito": "Credito"}
    contenido = xlsx(pd.DataFrame({"Código": ["1105", "2205"], "Débitos": [100, 0], "Créditos": [0, 100], "Saldo": [100, 100]}))
    perfil = PerfilImportacion(nombre="p", tipo="balance", mapeo={"cuenta": "Código", "debito": "Débitos", "credito": "Créditos", "saldo_final": "Saldo"})
    lectura = leer(contenido, "b.xlsx", "balance", perfil)
    assert not lectura.faltantes and len(lectura.filas) == 2 and lectura.filas[0]["debito"] == Decimal("100")


def test_faltantes_sin_mapeo():
    contenido = xlsx(pd.DataFrame({"A": [1], "B": [2]}))
    lectura = leer(contenido, "b.xlsx", "balance", None)
    assert lectura.faltantes


def test_csv_con_decimal_coma():
    csv = "Cuenta;Débito;Crédito;Saldo\n1105;1.000,50;0;1.000,50\n".encode()
    perfil = PerfilImportacion(nombre="c", tipo="balance", separador_csv=";", decimal_coma=True,
                               mapeo={"cuenta": "Cuenta", "debito": "Débito", "credito": "Crédito", "saldo_final": "Saldo"})
    lectura = leer(csv, "b.csv", "balance", perfil)
    assert lectura.filas[0]["debito"] == Decimal("1000.50")


@pytest.mark.django_db
def test_flujo_de_carga_y_vigencia(dueno):
    p = Periodo.obtener(2026, 9)
    df = pd.DataFrame({"cuenta": ["1105", "2205"], "debito": [100, 0], "credito": [0, 100], "saldo_final": [100, 100]})
    contenido = xlsx(df)  # una sola vez: el .xlsx lleva marca de tiempo y cambia de bytes entre llamadas
    subido = SimpleUploadedFile("balance.xlsx", contenido)
    a = cargas.registrar_archivo(subido, "balance", p, dueno)
    assert a.hash_sha256 and a.estado == "pendiente"
    a = cargas.confirmar(a, dueno)
    assert a.estado == "importado" and a.vigente and SaldoCuenta.objects.count() == 2
    # mismo archivo => duplicado
    with pytest.raises(cargas.ArchivoDuplicado):
        cargas.registrar_archivo(SimpleUploadedFile("otro.xlsx", contenido), "balance", p, dueno)
    # uno nuevo reemplaza como vigente, el anterior se conserva
    df2 = df.copy()
    df2.loc[0, "debito"] = 150
    b = cargas.confirmar(cargas.registrar_archivo(SimpleUploadedFile("b2.xlsx", xlsx(df2)), "balance", p, dueno), dueno)
    a.refresh_from_db()
    assert b.vigente and not a.vigente and ArchivoCargado.objects.count() == 2
    assert Cuenta.objects.count() == 2


@pytest.mark.django_db
def test_archivo_no_se_sobrescribe(dueno):
    p = Periodo.obtener(2026, 9)
    a = cargas.registrar_archivo(SimpleUploadedFile("x.csv", b"cuenta,debito,credito,saldo_final\n1,1,0,1\n"), "balance", p, dueno)
    a.hash_sha256 = "0" * 64
    with pytest.raises(ValueError):
        a.save()


@pytest.mark.django_db
def test_periodo_cerrado_bloquea(dueno):
    p = Periodo.obtener(2026, 8)
    p.estado = "cerrado"
    p.save()
    with pytest.raises(PeriodoCerrado):
        cargas.registrar_archivo(SimpleUploadedFile("x.csv", b"a,b\n1,2\n"), "balance", p, dueno)


@pytest.mark.django_db
def test_auxiliar_crea_terceros(dueno):
    p = Periodo.obtener(2026, 9)
    csv = "fecha,cuenta,nit,tercero_nombre,debito,credito,documento\n2026-09-02,5195,900123456-8,Proveedor Uno,100,0,FE-1\n".encode()
    a = cargas.registrar_archivo(SimpleUploadedFile("aux.csv", csv), "auxiliar", p, dueno)
    a = cargas.confirmar(a, dueno)
    assert a.estado == "importado"
    assert Movimiento.objects.get().nit == "900123456"
    assert Tercero.objects.get(nit="900123456").razon_social == "Proveedor Uno"


@pytest.mark.django_db
def test_errores_bloquean_salvo_omitir(dueno):
    p = Periodo.obtener(2026, 9)
    csv = "cuenta,debito,credito,saldo_final\n1105,10,0,10\n2205,xx,0,0\n".encode()
    a = cargas.registrar_archivo(SimpleUploadedFile("e.csv", csv), "balance", p, dueno)
    a = cargas.confirmar(a, dueno)
    assert a.estado == "error" and a.errores
    a = cargas.confirmar(a, dueno, omitir_filas_con_error=True)
    assert a.estado == "importado" and a.resumen["filas_omitidas"] == 1


@pytest.mark.django_db
def test_terceros_sueltos_se_filtran_y_se_limpian(cliente_dueno, dueno, datos_iniciales):
    from empresa.models import Periodo, RegistroAuditoria

    Tercero.objects.create(nit="800111222", razon_social="Proveedor Suelto", origen="factura")
    Tercero.objects.create(nit="800333444", razon_social="Proveedor Activo", origen="factura")
    p = Periodo.obtener(2026, 9)
    from tests.helpers import factura

    factura(p, "recibida", "1", date(2026, 9, 5), "800333444", "900902549", 1000, 190)
    html = cliente_dueno.get("/terceros/?anio=sin_movimiento").content.decode()
    assert "Proveedor Suelto" in html and "Proveedor Activo" not in html
    assert "Proveedor Activo" in cliente_dueno.get("/terceros/?anio=2026").content.decode()
    assert "Proveedor Suelto" not in cliente_dueno.get("/terceros/?anio=2026").content.decode()
    assert Tercero.objects.filter(nit="800111222").exists()
    cliente_dueno.post("/terceros/limpiar/")  # sin confirmar no borra
    assert Tercero.objects.filter(nit="800111222").exists()
    cliente_dueno.post("/terceros/limpiar/", {"entiendo": "1"})
    assert not Tercero.objects.filter(nit="800111222").exists() and Tercero.objects.filter(nit="800333444").exists()
    assert RegistroAuditoria.objects.filter(accion="eliminar", descripcion__contains="sin movimiento").exists()
    t = Tercero.objects.get(nit="800333444")
    cliente_dueno.post(f"/terceros/{t.pk}/eliminar/")
    assert not Tercero.objects.filter(nit="800333444").exists()


def _csv_terceros(filas):
    cab = "NIT,DV,Razón social,Tipo de persona,Dirección,Ciudad,Correo electrónico\n"
    return (cab + "\n".join(filas) + "\n").encode()


@pytest.mark.django_db
def test_maestro_de_terceros_completa_datos_vincula_nombres_y_no_pisa(dueno, datos_iniciales):
    from empresa.models import RegistroAuditoria

    p = Periodo.obtener(2026, 9)
    cargas_aux = SimpleUploadedFile("aux.csv", "fecha,cuenta,nit,tercero_nombre,debito,credito,documento\n2026-09-02,5195,,PROVEEDOR UNO S.A.S.,100,0,FE-1\n".encode())
    a = cargas.registrar_archivo(cargas_aux, "auxiliar", p, dueno)
    cargas.confirmar(a, dueno)
    assert Movimiento.objects.get(documento="FE-1").nit == ""
    Tercero.objects.create(nit="900111222", razon_social="Nombre editado a mano", direccion="CL 9 # 9-9", origen="factura")
    contenido = _csv_terceros([
        "900.123.456-8,,Proveedor Uno SAS,Jurídica,CL 1 # 2-3,Bogotá D.C.,uno@example.com",
        "900111222,,Otro nombre del maestro,Jurídica,CR 5 # 6-7,Medellín,",
        "sin-nit,,Fila mala,,,,",
    ])
    t = cargas.registrar_archivo(SimpleUploadedFile("terceros.csv", contenido), "terceros", p, dueno)
    t = cargas.confirmar(t, dueno, omitir_filas_con_error=True)
    assert t.estado == "importado", t.errores
    nuevo = Tercero.objects.get(nit="900123456")
    assert nuevo.dv == "8" and nuevo.ciudad == "Bogotá D.C." and nuevo.tipo_persona == "juridica" and nuevo.origen == "maestro"
    previo = Tercero.objects.get(nit="900111222")
    assert previo.razon_social == "Nombre editado a mano" and previo.direccion == "CL 9 # 9-9"  # no pisa lo que ya tenía
    assert previo.ciudad == "Medellín" and previo.tipo_persona == "juridica"  # sí llena lo vacío
    r = t.resumen
    assert r["terceros_nuevos"] == 1 and r["terceros_actualizados"] == 1 and r["con_datos_distintos_no_cambiados"] == 1
    assert r["movimientos_con_nit"] == 1 and Movimiento.objects.get(documento="FE-1").nit == "900123456"
    assert RegistroAuditoria.objects.filter(descripcion__contains="NIT del maestro").exists()
    # un auxiliar que se cargue después ya trae el NIT por el nombre
    aux2 = SimpleUploadedFile("aux2.csv", "fecha,cuenta,nit,tercero_nombre,debito,credito,documento\n2026-09-03,5195,,Proveedor Uno SAS,50,0,FE-2\n".encode())
    cargas.confirmar(cargas.registrar_archivo(aux2, "auxiliar", p, dueno), dueno)
    assert Movimiento.objects.get(documento="FE-2").nit == "900123456"


@pytest.mark.django_db
def test_carga_de_terceros_no_pide_mes_y_rechaza_archivos_de_otro_tipo(cliente_dueno, datos_iniciales):
    ok = cliente_dueno.post("/cargas/nueva/", {"tipo": "terceros", "archivo": SimpleUploadedFile("t.csv", _csv_terceros(["900123456,8,Uno SAS,Jurídica,CL 1,Bogotá,"]))})
    assert ok.status_code == 302 and "/cargas/" in ok.url
    mal = cliente_dueno.post("/cargas/nueva/", {"tipo": "terceros", "archivo": SimpleUploadedFile("m.csv", b"fecha,cuenta,debito,credito\n2026-09-01,5195,10,0\n")})
    assert mal.status_code == 200 and "débitos y créditos" in mal.content.decode()
    assert cliente_dueno.get("/terceros/plantilla/").status_code == 200
    assert "Cargar maestro de terceros" in cliente_dueno.get("/terceros/").content.decode()


def test_norm_nombre_trata_sas_con_puntos_igual_que_sas():
    from controles.reglas_facturas import norm_nombre

    assert norm_nombre("PROVEEDOR UNO S.A.S.") == norm_nombre("Proveedor Uno SAS") == "PROVEEDORUNO"
    assert norm_nombre("Comercial Dos S.A.") == norm_nombre("COMERCIAL DOS SA")


def _xlsx(columnas):
    import io

    import pandas as pd

    b = io.BytesIO()
    pd.DataFrame(columnas).to_excel(b, index=False)
    return b.getvalue()


@pytest.mark.django_db
def test_extracto_en_excel_con_debitos_y_creditos_separados(dueno, datos_iniciales):
    from conciliaciones.models import MovimientoBanco

    p = Periodo.obtener(2026, 9)
    contenido = _xlsx({"FECHA": ["2026-09-02", "2026-09-03"], "DESCRIPCION": ["PAGO PROVEEDOR", "ABONO CLIENTE"],
                       "DEBITOS": [1000.0, 0.0], "CREDITOS": [0.0, 2500.0], "SALDO": [4000.0, 6500.0]})
    a = cargas.registrar_archivo(SimpleUploadedFile("extracto.xlsx", contenido), "extracto_banco", p, dueno)
    a = cargas.confirmar(a, dueno)
    assert a.estado == "importado", a.errores
    valores = sorted(MovimientoBanco.objects.filter(archivo=a).values_list("valor", flat=True))
    assert valores == [Decimal("-1000"), Decimal("2500")]  # los cargos restan y los abonos suman


@pytest.mark.django_db
def test_extracto_en_excel_con_una_columna_de_valor_y_pantalla_con_boton(cliente_dueno, dueno, datos_iniciales):
    from conciliaciones.models import MovimientoBanco

    p = Periodo.obtener(2026, 9)
    contenido = _xlsx({"Fecha": ["2026-09-02"], "Descripción": ["PAGO"], "Valor": [-1000.0], "Saldo": [5000.0]})
    a = cargas.confirmar(cargas.registrar_archivo(SimpleUploadedFile("e2.xlsx", contenido), "extracto_banco", p, dueno), dueno)
    assert MovimientoBanco.objects.get(archivo=a).valor == Decimal("-1000")
    assert "Cargar extracto bancario" in cliente_dueno.get("/conciliaciones/").content.decode()
    assert "extracto" in cliente_dueno.get("/cargas/nueva/?tipo=extracto_banco").content.decode().lower()


@pytest.mark.django_db
def test_declaraciones_incluyen_reteica_y_las_dos_exogenas(cliente_dueno, datos_iniciales):
    from empresa.forms import CargaForm

    claves = {k for k, _ in CargaForm().fields["formulario"].choices}
    assert {"ica", "reteica", "350", "300", "110", "exo_dist", "exo_dian"} <= claves
    assert all(len(k) <= 10 for k in claves)  # cabe en ArchivoCargado.formulario
