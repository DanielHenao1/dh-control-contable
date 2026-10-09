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


@pytest.mark.django_db
def test_enero_2026_muestra_los_impuestos_de_2025_pagados(datos_iniciales, cliente_dueno):
    # En enero de 2026 vencieron la retención de dic-2025 y el IVA del 3.er cuatrimestre de 2025
    ret = Obligacion.objects.get(tipo="retefuente", clave="2025-12")
    iva = Obligacion.objects.get(tipo="iva", clave="2025-P3")
    assert ret.fecha_limite.year == 2026 and ret.fecha_limite.month == 1 and ret.estado == "pagada"
    assert iva.fecha_limite.year == 2026 and iva.fecha_limite.month == 1 and iva.estado == "pagada"
    # Renta del año gravable 2025: se declaró y pagó en 2026
    assert Obligacion.objects.get(tipo="renta_c1", clave="2025").estado == "pagada"
    assert Obligacion.objects.get(tipo="renta_c2", clave="2025").estado == "pagada"
    # Nada anterior a CALENDARIO_DESDE (2026-01-01) y sin pendientes de impuestos hasta el 9-oct-2026
    assert not Obligacion.objects.filter(fecha_limite__lt=date(2026, 1, 1)).exists()
    # Sin fecha no se crea nada de años anteriores a 2026 (la exógena AG 2025 sí existe, con su fecha publicada)
    assert not Obligacion.objects.filter(clave="2025", fecha_limite__isnull=True).exists()
    assert not Obligacion.objects.filter(
        tipo__in=["retefuente", "iva", "ica", "reteica", "renta_c1", "renta_c2"], fecha_limite__lte=date(2026, 10, 9)
    ).exclude(estado="pagada").exists()
    html = cliente_dueno.get("/calendario/?anio=2026&mes=1").content.decode()
    assert "Retención en la fuente" in html and "Presentada y pagada" in html


@pytest.mark.django_db
def test_ica_y_reteica_de_bogota_completos(datos_iniciales):
    ica = {o.clave: o for o in Obligacion.objects.filter(tipo="ica")}
    esperadas = {
        "2025-B6": date(2026, 2, 13), "2026-B1": date(2026, 4, 10), "2026-B2": date(2026, 6, 12),
        "2026-B3": date(2026, 8, 21), "2026-B4": date(2026, 10, 9), "2026-B5": date(2026, 12, 11),
        "2026-B6": date(2027, 2, 12), "2026-anual": date(2027, 2, 26),
    }
    assert {k: v.fecha_limite for k, v in ica.items()} == esperadas
    rete = {o.clave: o for o in Obligacion.objects.filter(tipo="reteica")}
    assert {k: v.fecha_limite for k, v in rete.items()} == {
        "2025-B6": date(2026, 1, 16), "2026-B1": date(2026, 3, 20), "2026-B2": date(2026, 5, 22),
        "2026-B3": date(2026, 7, 17), "2026-B4": date(2026, 9, 18), "2026-B5": date(2026, 11, 20),
        "2026-B6": date(2027, 1, 15),
    }
    # Todo lo vencido hasta el 9-oct-2026 está presentado y pagado; lo posterior sigue pendiente
    for o in list(ica.values()) + list(rete.values()):
        esperado = "pagada" if o.fecha_limite <= date(2026, 10, 9) else "pendiente"
        assert o.estado == esperado, (o.tipo, o.clave)
    # Las que solo tienen una fuente quedan marcadas como tales (no se presentan como verificadas)
    assert rete["2026-B5"].verificacion == "una_fuente" and rete["2026-B1"].verificacion == "dos_fuentes"


@pytest.mark.django_db
def test_logo_y_favicon_en_las_paginas(cliente_dueno, datos_iniciales):
    html = cliente_dueno.get("/").content.decode()
    assert "img/favicon.ico" in html and "img/logo-dhstore-claro.png" in html and "apple-touch-icon" in html
    from django.contrib.staticfiles import finders

    for ruta in ("img/favicon.ico", "img/icon-180.png", "img/icon-32.png", "img/logo-dhstore.png", "img/logo-dhstore-claro.png"):
        assert finders.find(ruta), ruta


@pytest.mark.django_db
def test_exogena_nacional_y_distrital(datos_iniciales):
    nacional = Obligacion.objects.get(tipo="exogena", clave="2025")
    assert nacional.fecha_limite == date(2026, 5, 28) and nacional.verificacion == "dos_fuentes"
    distrital = Obligacion.objects.get(tipo="exogena_distrital", clave="2025")
    assert distrital.fecha_limite == date(2026, 10, 26) and distrital.estado == "pendiente"
    assert "DDI-024115" in distrital.fuente
    # Año gravable 2026 (se reporta en 2027): sin fecha publicada, no se inventa
    for tipo in ("exogena", "exogena_distrital"):
        assert Obligacion.objects.get(tipo=tipo, clave="2026").fecha_limite is None
    # El distrital vence después de CONTROL_DESDE: sí genera alertas
    from calendario.alertas import obligaciones_a_alertar

    assert any(o.tipo == "exogena_distrital" and d == 7 for o, d in obligaciones_a_alertar(date(2026, 10, 19)))


@pytest.mark.django_db
def test_selector_desplegable_de_anio_y_mes(cliente_dueno, datos_iniciales):
    html = cliente_dueno.get("/calendario/?anio=2026&mes=10").content.decode()
    assert 'id="picker-cal"' in html
    # Un enlace por cada mes del año elegido y por cada año disponible
    for m in range(1, 13):
        assert f"anio=2026&mes={m}" in html
    for a in (2025, 2026, 2027):
        assert f"anio={a}&mes=10" in html
    # Octubre 2026 tiene pendiente la retención del 22-oct: el mes lo marca
    assert 'title="' in html and "pendiente(s)" in html
    assert "Ir a hoy" in html and "2.026" not in html
    # Valores fuera de rango no rompen la página
    assert cliente_dueno.get("/calendario/?anio=2026&mes=13").status_code == 200
    assert cliente_dueno.get("/calendario/?anio=abc&mes=x").status_code == 200
