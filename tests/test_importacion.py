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
