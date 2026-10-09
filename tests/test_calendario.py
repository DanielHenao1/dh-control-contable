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
