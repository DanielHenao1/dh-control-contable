from datetime import date

import pytest
from django.core import mail

from calendario.alertas import enviar_alertas, obligaciones_a_alertar
from calendario.generador import generar_obligaciones
from calendario.models import Obligacion, ReglaVencimiento
from empresa.models import Empresa, Parametro


@pytest.mark.django_db
def test_calendario_del_plan(datos_iniciales):
    o = Obligacion.objects.get(tipo="retefuente", clave="2026-09")
    assert o.fecha_limite == date(2026, 10, 22)
    assert o.verificacion == "dos_fuentes"
    assert o.estado == "pendiente" and "Ideako" in o.notas
    assert Obligacion.objects.get(tipo="iva", clave="2026-P3").fecha_limite == date(2027, 1, 25)
    assert Obligacion.objects.get(tipo="renta_c1", clave="2026").fecha_limite == date(2027, 5, 24)
    ica = Obligacion.objects.get(tipo="ica", clave="2026-B4")
    assert ica.fecha_limite == date(2026, 10, 9) and ica.estado == "pagada"
    assert Obligacion.objects.get(tipo="exogena", clave="2026").fecha_limite is None
    assert Obligacion.objects.get(tipo="cesantias_intereses", clave="2027-ene").laboral


@pytest.mark.django_db
def test_sin_regla_para_otros_digitos_no_inventa_fechas(datos_iniciales):
    Empresa.objects.update(nit="900902541")  # termina en 1: no hay regla verificada
    Obligacion.objects.filter(tipo="retefuente").delete()
    generar_obligaciones(2026, 2026)
    o = Obligacion.objects.get(tipo="retefuente", clave="2026-03")
    assert o.fecha_limite is None and "regla" in o.notas


@pytest.mark.django_db
def test_periodicidad_bimestral_es_parametro(datos_iniciales):
    Parametro.objects.filter(codigo="IVA_PERIODICIDAD").update(valor="bimestral")
    Obligacion.objects.filter(tipo="iva").delete()
    generar_obligaciones(2026, 2026)
    assert Obligacion.objects.filter(tipo="iva", clave__startswith="2026-P").count() == 6


@pytest.mark.django_db
def test_regla_mantiene_verificacion_manual(datos_iniciales):
    generar_obligaciones(2026, 2027)
    assert Obligacion.objects.get(tipo="retefuente", clave="2026-10").verificacion == "dos_fuentes"
    assert Obligacion.objects.get(tipo="retefuente", clave="2027-02").verificacion == "regla"
    assert ReglaVencimiento.objects.filter(modo="dia_habil").count() == 4


@pytest.mark.django_db
def test_alertas_por_correo(datos_iniciales, dueno):
    hoy = date(2026, 10, 19)  # 3 días antes del 22
    pendientes = obligaciones_a_alertar(hoy)
    assert any(o.clave == "2026-09" and d == 3 for o, d in pendientes)
    n = enviar_alertas(hoy)
    assert n >= 1 and len(mail.outbox) == 1
    assert "Retención en la fuente" in mail.outbox[0].body
    assert enviar_alertas(hoy) == 0  # no repite el mismo día


@pytest.mark.django_db
def test_historico_no_cuenta_como_vencido(datos_iniciales, cliente_dueno):
    from calendario.alertas import obligaciones_a_alertar
    from calendario.historico import control_desde, solo_vigentes

    assert control_desde() == date(2026, 10, 1)
    # Las declaraciones previas quedaron como presentadas; la de septiembre sigue pendiente
    assert Obligacion.objects.get(tipo="retefuente", clave="2026-08").estado == "pagada"
    assert Obligacion.objects.get(tipo="iva", clave="2026-P2").estado == "pagada"
    assert Obligacion.objects.get(tipo="ica", clave="2026-B4").estado == "pagada"
    assert Obligacion.objects.get(tipo="retefuente", clave="2026-09").estado == "pendiente"
    # Ningún impuesto con vencimiento hasta el 9-oct-2026 queda pendiente
    assert not Obligacion.objects.filter(
        tipo__in=["retefuente", "iva", "ica"], fecha_limite__lte=date(2026, 10, 9)
    ).exclude(estado="pagada").exists()
    m = Obligacion.objects.get(tipo="matricula", clave="2026")
    assert m.estado == "pagada" and "29-abr-2026" in m.notas
    assert Obligacion.objects.get(tipo="matricula", clave="2027").estado == "pendiente"
    # Lo anterior a CONTROL_DESDE se excluye aunque siga pendiente (p. ej. fechas laborales)
    pasadas = Obligacion.objects.filter(fecha_limite__lt=date(2026, 10, 1), estado="pendiente")
    assert pasadas.exists()
    assert not solo_vigentes(pasadas).exists()
    assert not any(o.fecha_limite < date(2026, 10, 1) for o, _ in obligaciones_a_alertar(date(2026, 10, 19)))


@pytest.mark.django_db
def test_hallazgos_de_calendario_ignoran_el_historico(datos_iniciales):
    from django.utils import timezone

    from controles.models import Hallazgo
    from controles.motor import ejecutar_reglas

    from .helpers import periodo

    hoy = timezone.localdate()
    ejecutar_reglas(periodo(hoy.year, hoy.month), codigos=["CAL001", "CAL003", "CAL005"])
    for h in Hallazgo.objects.filter(regla__grupo="calendario"):
        assert "2026-01" not in h.clave and "2026-02" not in h.clave and "2026-P1" not in h.clave


@pytest.mark.django_db
def test_navegacion_de_meses_y_anios(cliente_dueno, datos_iniciales):
    r = cliente_dueno.get("/calendario/?anio=2026&mes=11")
    html = r.content.decode()
    assert "Noviembre" in html and "Octubre 2026" not in html
    assert "2.026" not in html  # el año nunca debe llevar separador de miles
    assert "anio=2026&mes=12" in html and "anio=2026&mes=10" in html
    r = cliente_dueno.get("/calendario/?anio=2027&mes=1")
    assert "Enero" in r.content.decode() and "anio=2027&mes=2" in r.content.decode()
    # El selector del tablero también debe enviar el año como número simple
    t = cliente_dueno.get("/?anio=2027&mes=3").content.decode()
    assert 'value="2027" selected' in t and "2.027" not in t


@pytest.mark.django_db
def test_calendario_se_genera_solo_al_cambiar_de_anio(datos_iniciales, monkeypatch):
    from calendario import tasks

    assert not Obligacion.objects.filter(tipo="retefuente", clave="2028-01").exists()
    monkeypatch.setattr(tasks.timezone, "localdate", lambda: date(2027, 12, 20))
    n = tasks.generar_calendario_automatico()
    assert n > 0
    o = Obligacion.objects.get(tipo="retefuente", clave="2028-01")
    assert o.fecha_limite is not None and o.fecha_limite.year == 2028
    assert tasks.generar_calendario_automatico() == 0  # idempotente
