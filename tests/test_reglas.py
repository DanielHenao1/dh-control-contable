from datetime import date
from decimal import Decimal

import pytest

from controles.models import Hallazgo
from controles.motor import ejecutar_reglas
from empresa.models import Parametro
from impuestos.models import ConceptoRetencion, Declaracion, DiferenciaFiscal
from terceros.models import Tercero

from .helpers import auxiliar, balance, factura, periodo, retencion

P = date(2026, 9, 1)


def hallazgos(p, codigo):
    return list(Hallazgo.objects.filter(periodo=p, regla__codigo=codigo))


@pytest.mark.django_db
def test_integridad_balance(datos_iniciales):
    p = periodo()
    balance(p, [
        ("1105", "Caja", 0, 100, 0, 100),
        ("2205", "Proveedores", 0, 0, 90, 90),     # descuadra 10
        ("1305", "Clientes", 0, 0, 50, 50),         # saldo calculado -50 vs 50 y naturaleza
    ])
    ejecutar_reglas(p)
    assert len(hallazgos(p, "INT001")) == 1
    assert {h.clave for h in hallazgos(p, "INT002")} == {"1305"}
    assert hallazgos(p, "INT004")  # falta auxiliar


@pytest.mark.django_db
def test_naturaleza_contraria(datos_iniciales):
    p = periodo()
    balance(p, [("1105", "Caja", 0, 0, 0, -500), ("2205", "Proveedores", 0, 0, 0, 100)])
    ejecutar_reglas(p, codigos=["INT003"])
    assert [h.clave for h in hallazgos(p, "INT003")] == ["1105"]


@pytest.mark.django_db
def test_reejecutar_no_duplica_y_corrige(datos_iniciales):
    p = periodo()
    a = balance(p, [("1105", "Caja", 0, 0, 0, -500)])
    ejecutar_reglas(p, codigos=["INT003"])
    ejecutar_reglas(p, codigos=["INT003"])
    assert Hallazgo.objects.filter(regla__codigo="INT003").count() == 1
    a.saldos.update(saldo_final=500)
    r = ejecutar_reglas(p, codigos=["INT003"])
    assert r["corregidos"] == 1 and Hallazgo.objects.get(regla__codigo="INT003").estado == "corregido"


@pytest.mark.django_db
def test_asiento_descuadrado_y_duplicado(datos_iniciales):
    p = periodo()
    auxiliar(p, [
        (date(2026, 9, 1), "CP-1", "FE1", "5195", "900111", 100, 0),
        (date(2026, 9, 1), "CP-1", "FE1", "2205", "900111", 0, 90),
        (date(2026, 9, 2), "CP-2", "FE1", "5195", "900111", 100, 0),
    ])
    ejecutar_reglas(p, codigos=["INT005", "INT006"])
    assert {h.clave for h in hallazgos(p, "INT005")} == {"CP-1", "CP-2"}
    assert len(hallazgos(p, "INT006")) == 1


@pytest.mark.django_db
def test_facturas_sin_causar_y_valor_distinto(datos_iniciales):
    p = periodo()
    factura(p, "recibida", "100", date(2026, 9, 5), "900111", "900902549", 1000, 190, prefijo="FE")
    factura(p, "recibida", "101", date(2026, 9, 6), "900111", "900902549", 2000, 380, prefijo="FE")
    factura(p, "recibida", "102", date(2026, 9, 7), "900222", "900902549", 500, 95, prefijo="FE")
    auxiliar(p, [
        (date(2026, 9, 5), "CP-1", "FE100", "2205", "900111", 0, 1190),   # bien
        (date(2026, 9, 6), "CP-2", "FE101", "2205", "900111", 0, 2000),   # valor distinto (total 2380)
    ])
    ejecutar_reglas(p, codigos=["FAC001", "FAC002"])
    assert [h.clave for h in hallazgos(p, "FAC001")] == ["recibida|900222|FE102"]
    assert [h.clave for h in hallazgos(p, "FAC002")] == ["recibida|900111|FE101"]


@pytest.mark.django_db
def test_facturas_duplicadas_notas_y_numeracion(datos_iniciales):
    p = periodo()
    factura(p, "emitida", "1", date(2026, 9, 1), "900902549", "800111", 100, 19, prefijo="SETP")
    factura(p, "emitida", "2", date(2026, 9, 2), "900902549", "800111", 100, 19, prefijo="SETP")
    factura(p, "emitida", "5", date(2026, 9, 3), "900902549", "800111", 100, 19, prefijo="SETP")
    factura(p, "emitida", "5", date(2026, 9, 3), "900902549", "800111", 100, 19, prefijo="SETP")
    factura(p, "emitida", "9", date(2026, 9, 4), "900902549", "800111", 100, 19, prefijo="NC", tipo="nota_credito")
    factura(p, "emitida", "7", date(2026, 10, 4), "900902549", "800111", 100, 19, prefijo="SETP")
    ejecutar_reglas(p, codigos=["FAC003", "FAC004", "FAC005", "FAC006"])
    assert len(hallazgos(p, "FAC003")) == 1
    assert len(hallazgos(p, "FAC004")) == 1
    assert len(hallazgos(p, "FAC005")) == 1
    assert "Faltan 3" in hallazgos(p, "FAC006")[0].detalle  # faltan 3, 4 y 6


def completar_anio(p):
    """Auxiliares vigentes de los 12 meses del año: desde ahí aplican los controles de exógena."""
    from empresa.models import Periodo

    from .helpers import archivo

    for mes in range(1, 13):
        if mes != p.mes:
            archivo("auxiliar", Periodo.obtener(p.anio, mes))


@pytest.mark.django_db
def test_tercero_dv_y_datos(datos_iniciales):
    p = periodo()
    completar_anio(p)
    Tercero.objects.create(nit="900902549", dv="3", razon_social="X")
    Tercero.objects.create(nit="800197268", dv="4", razon_social="DIAN", direccion="Cra", ciudad="Bogotá", tipo_persona="juridica")
    auxiliar(p, [(date(2026, 9, 1), "C1", "D1", "5195", "900902549", 1, 0), (date(2026, 9, 1), "C1", "D1", "2205", "800197268", 0, 1)])
    ejecutar_reglas(p, codigos=["TER001", "TER002"])
    assert [h.clave for h in hallazgos(p, "TER001")] == ["900902549"]
    assert [h.clave for h in hallazgos(p, "TER002")] == ["900902549"]


def cargar_concepto(tarifa_decl="4", tarifa_no="7", base_uvt="27"):
    ConceptoRetencion.objects.create(
        codigo="COMPRAS", nombre="Compras", base_minima_uvt=Decimal(base_uvt), tarifa_declarante=Decimal(tarifa_decl),
        tarifa_no_declarante=Decimal(tarifa_no), vigente_desde=date(2026, 1, 1), estado="verificado",
    )


@pytest.mark.django_db
def test_retencion_teorica(datos_iniciales):
    p = periodo()
    cargar_concepto()   # base mínima 27 UVT = 1.414.098
    Tercero.objects.create(nit="900111", es_declarante=True)
    Tercero.objects.create(nit="900222", es_declarante=False)
    retencion(p, date(2026, 9, 3), "900111", "COMPRAS", 2_000_000, 4, 80_000, doc="A")     # ok
    retencion(p, date(2026, 9, 4), "900111", "COMPRAS", 2_000_000, 4, 40_000, doc="B")     # retenido < teórico
    retencion(p, date(2026, 9, 5), "900111", "COMPRAS", 1_000_000, 4, 40_000, doc="C")     # bajo base mínima
    retencion(p, date(2026, 9, 6), "900222", "COMPRAS", 2_000_000, 4, 80_000, doc="D")     # no declarante: debía ser 7% y tarifa aplicada 4
    retencion(p, date(2026, 9, 7), "900111", "SERVICIOS", 5_000_000, 4, 200_000, doc="E")  # sin tarifa
    ejecutar_reglas(p, codigos=["RET001", "RET002", "RET003", "RET004"])
    assert {h.titulo.split(" en ")[-1] for h in hallazgos(p, "RET001")} == {"B", "D"}
    assert [h.cifras["retenido"] for h in hallazgos(p, "RET002")] == ["40000.00"]
    assert len(hallazgos(p, "RET003")) == 1
    assert [h.clave for h in hallazgos(p, "RET004")] == ["SERVICIOS"]


@pytest.mark.django_db
def test_retencion_contabilidad_vs_declarado(datos_iniciales):
    p = periodo()
    retencion(p, date(2026, 9, 3), "900111", "COMPRAS", 2_000_000, 4, 80_000)
    balance(p, [("236540", "Retefuente compras", 0, 0, 70_000, 70_000)])
    Declaracion.objects.create(tipo="retefuente", anio=2026, indice=9, valor_declarado=Decimal("60000"))
    ejecutar_reglas(p, codigos=["RET005", "RET006"])
    assert len(hallazgos(p, "RET005")) == 1
    assert len(hallazgos(p, "RET006")) == 1


@pytest.mark.django_db
def test_iva_fe_vs_contabilidad_y_declarado(datos_iniciales):
    Parametro.objects.filter(codigo="PUC_IVA_GENERADO").update(valor="240801")
    Parametro.objects.filter(codigo="PUC_IVA_DESCONTABLE").update(valor="240802")
    p = periodo(2026, 12)
    factura(p, "emitida", "1", date(2026, 12, 5), "900902549", "800111", 1000, 190, prefijo="V")
    factura(p, "recibida", "9", date(2026, 12, 6), "900111", "900902549", 500, 95, prefijo="F")
    balance(p, [("240801", "IVA generado", 0, 0, 150, 150), ("240802", "IVA descontable", 0, 95, 0, 95)])
    Declaracion.objects.create(tipo="iva", anio=2026, indice=3, valor_declarado=Decimal("50"))
    ejecutar_reglas(p, codigos=["IVA001", "IVA002"])
    assert [h.clave for h in hallazgos(p, "IVA001")] == ["generado"]
    h = hallazgos(p, "IVA002")[0]
    assert h.cifras["propio"] == "95.00" and h.cifras["declarado"] == "50.00"


@pytest.mark.django_db
def test_iva_periodicidad(datos_iniciales):
    p = periodo(2026, 12)
    # 92.000 UVT × 52.374 = 4.818.408.000; ingresos 5.000 millones
    balance(p, [("4135", "Ventas", 0, 0, 5_000_000_000, 5_000_000_000)])
    ejecutar_reglas(p, codigos=["IVA003"])
    h = hallazgos(p, "IVA003")
    assert h and "bimestral" in h[0].titulo


@pytest.mark.django_db
def test_renta_reglas(datos_iniciales):
    p = periodo(2026, 12)
    balance(p, [("4135", "Ventas", 0, 0, 1_000_000, 1_000_000), ("5195", "Gastos", 0, 400_000, 0, 400_000)])
    auxiliar(p, [(date(2026, 12, 1), "C1", "", "5195", "", 400_000, 0)])
    DiferenciaFiscal.objects.create(anio=2026, concepto="Multas", tipo="perm_mas", valor=Decimal("10000"))
    ejecutar_reglas(p, codigos=["REN001", "REN003"])
    assert len(hallazgos(p, "REN001")) == 1
    assert len(hallazgos(p, "REN003")) == 1


@pytest.mark.django_db
def test_exogena_sin_tope_avisa(datos_iniciales):
    p = periodo()
    auxiliar(p, [(date(2026, 9, 1), "C0", "D0", "5195", "900333", 0, 0)])
    ejecutar_reglas(p, codigos=["EXO001"])
    assert hallazgos(p, "EXO001") == []  # con solo septiembre cargado la exógena no se evalúa
    completar_anio(p)
    ejecutar_reglas(p, codigos=["EXO001"])
    assert hallazgos(p, "EXO001")[0].clave == "sin-tope"
    Parametro.objects.filter(codigo="EXOGENA_TOPE_PESOS").update(valor="1000000", estado="verificado")
    auxiliar(p, [(date(2026, 9, 1), "C1", "D1", "5195", "900333", 2_000_000, 0)])
    ejecutar_reglas(p, codigos=["EXO001"])
    ab = Hallazgo.objects.filter(regla__codigo="EXO001", estado="abierto")
    assert [h.clave for h in ab] == ["900333"]


@pytest.mark.django_db
def test_calendario_reglas_solo_periodo_actual(datos_iniciales):
    from django.utils import timezone

    hoy = timezone.localdate()
    p = periodo(hoy.year, hoy.month)
    ejecutar_reglas(p, codigos=["CAL005"])
    otro = periodo(2020, 1)
    ejecutar_reglas(otro, codigos=["CAL005"])
    assert not Hallazgo.objects.filter(periodo=otro).exists()


@pytest.mark.django_db
def test_cierre_depreciacion_y_provisiones(datos_iniciales):
    p = periodo()
    balance(p, [
        ("152405", "Equipo", 0, 0, 0, 5_000_000), ("516005", "Depreciación", 0, 0, 0, 0),
        ("510506", "Sueldos", 0, 3_000_000, 0, 3_000_000), ("250505", "Cesantías", 0, 0, 0, 0),
    ])
    ejecutar_reglas(p, codigos=["CIE001", "NOM001"])
    assert len(hallazgos(p, "CIE001")) == 1 and len(hallazgos(p, "NOM001")) == 1
    p2 = periodo(2026, 10)
    balance(p2, [("152405", "Equipo", 0, 0, 0, 5_000_000), ("516005", "Depreciación", 0, 50_000, 0, 50_000),
                 ("510506", "Sueldos", 0, 3_000_000, 0, 3_000_000), ("250505", "Cesantías", 0, 0, 250_000, 250_000)])
    ejecutar_reglas(p2, codigos=["CIE001", "NOM001"])
    assert not hallazgos(p2, "CIE001") and not hallazgos(p2, "NOM001")


@pytest.mark.django_db
def test_iva_descontable_con_saldo_debito_no_es_naturaleza_contraria(datos_iniciales):
    from controles.reglas_integridad import naturaleza_contraria
    from empresa.models import Parametro

    from .helpers import balance, periodo

    p = periodo()
    balance(p, [("240802", "IVA descontable", 0, 703000, 0, -703000), ("220505", "Proveedores", 0, 0, 100, -100)])
    # la cuenta 2408 (IVA) y la depreciación acumulada (1592) llevan saldo contrario por diseño; el proveedor no
    assert {r.clave for r in naturaleza_contraria(p)} == {"220505"}
    balance(p, [("159205", "Depreciación acumulada", 0, 0, 0, -500), ("240802", "IVA descontable", 0, 703000, 0, -703000)])
    assert {r.clave for r in naturaleza_contraria(p)} == {"220505"}
    Parametro.objects.filter(codigo="PUC_CUENTAS_CONTRA").update(valor="9999", estado="verificado")
    assert {r.clave for r in naturaleza_contraria(p)} >= {"220505", "159205"}


@pytest.mark.django_db
def test_exogena_cierra_lo_abierto_mientras_falte_el_anio(datos_iniciales):
    """Hallazgos de exógena creados con el año completo se cierran con motivo si luego deja de estarlo."""
    from empresa.models import ArchivoCargado

    p = periodo()
    Tercero.objects.create(nit="900902549", dv="3", razon_social="X")
    auxiliar(p, [(date(2026, 9, 1), "C1", "D1", "5195", "900902549", 1, 0)])
    completar_anio(p)
    ejecutar_reglas(p, codigos=["TER002"])
    assert [h.estado for h in hallazgos(p, "TER002")] == ["abierto"]
    ArchivoCargado.objects.filter(tipo="auxiliar", periodo__mes=3).delete()
    ejecutar_reglas(p, codigos=["TER002"])
    h = hallazgos(p, "TER002")[0]
    assert h.estado == "corregido" and "Todavía no aplica" in h.explicacion


@pytest.mark.django_db
def test_cargar_datos_iniciales_recalcula_los_controles_de_los_periodos_con_datos(datos_iniciales):
    from django.core.management import call_command

    p = periodo()
    Tercero.objects.create(nit="900902549", dv="3", razon_social="X")
    auxiliar(p, [(date(2026, 9, 1), "C1", "D1", "5195", "900902549", 1, 0)])
    completar_anio(p)
    ejecutar_reglas(p, codigos=["TER002"])
    assert hallazgos(p, "TER002")[0].estado == "abierto"
    from empresa.models import ArchivoCargado

    ArchivoCargado.objects.filter(tipo="auxiliar", periodo__mes=3).delete()  # el año deja de estar completo
    call_command("cargar_datos_iniciales")
    assert hallazgos(p, "TER002")[0].estado == "corregido"


@pytest.mark.django_db
def test_plan_de_cuentas_llena_los_parametros_sin_pisar_lo_editado(datos_iniciales):
    from django.core.management import call_command

    from empresa.models import Parametro

    def p(codigo):
        return Parametro.objects.get(codigo=codigo, vigente_hasta__isnull=True)

    assert p("PUC_IVA_DESCONTABLE").valor == "240802" and p("PUC_IVA_DESCONTABLE").estado == "verificado"
    assert p("PUC_CARTERA").valor == "1305" and p("PUC_CAJA_BANCOS").valor == "1105,1110,1120"
    assert p("PUC_PASIVO_CORRIENTE").estado == "por_verificar" and p("PUC_PASIVO_CORRIENTE").valor  # propuesta pendiente
    Parametro.objects.filter(codigo="PUC_INGRESOS").update(valor="41,42", estado="por_verificar")  # alguien lo editó
    Parametro.objects.filter(codigo="PUC_CARTERA").update(valor="1305,1380", estado="verificado")
    call_command("cargar_datos_iniciales")
    assert p("PUC_INGRESOS").valor == "41,42" and p("PUC_CARTERA").valor == "1305,1380"
