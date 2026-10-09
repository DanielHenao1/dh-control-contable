from datetime import timedelta

import pytest
from django.utils import timezone

from calendario.models import Obligacion


def crear(tipo, clave, dias, estado="pendiente", nombre="Retención en la fuente"):
    hoy = timezone.localdate()
    return Obligacion.objects.create(
        tipo=tipo, clave=clave, nombre=nombre, periodo_texto=clave, fecha_limite=hoy + timedelta(days=dias), estado=estado
    )


@pytest.mark.django_db
def test_semaforo_urgencia_y_dias():
    pend = crear("retefuente", "a", 3)
    futura = crear("iva", "b", 20)
    pres = crear("ica", "c", 2, estado="presentada")
    pagada = crear("ica", "d", -5, estado="pagada")
    vencida = crear("iva", "e", -1)
    assert [o.semaforo for o in (pend, futura, pres, pagada, vencida)] == ["naranja", "naranja", "azul", "verde", "rojo"]
    assert vencida.etiqueta == "Vencida" and pend.etiqueta == "Pendiente" and pres.etiqueta == "Presentada"
    exogena = crear("exogena", "x", -30, estado="presentada")
    assert exogena.semaforo == "verde"  # informativa: presentarla basta
    assert pend.urgente and not futura.urgente and not pres.urgente and not pagada.urgente
    assert pend.dias_restantes == 3 and pagada.dias_restantes == -5


@pytest.mark.django_db
def test_alerta_solo_lo_que_vence_en_los_proximos_20_dias(cliente_dueno):
    crear("retefuente", "p1", 5)
    crear("iva", "limite", 20, nombre="IVA en 20 días")
    crear("iva", "lejos", 21, nombre="Renta en 21 días")
    crear("iva", "vencida", -3, nombre="Prima vencida")
    crear("ica", "ok", 1, estado="pagada", nombre="ICA pagado")
    for url in ("/", "/calendario/"):
        html = cliente_dueno.get(url).content.decode()
        assert 'id="alerta-venc"' in html and 'class="alerta-panel"' in html, url
        alerta = html[html.index('class="alerta-panel"'):html.index("</dialog>")]
        assert "Retención en la fuente" in alerta and "Vence en 5 día(s)" in alerta and "IVA en 20 días" in alerta
        assert "próximos 20 días" in alerta
        assert "Renta en 21 días" not in alerta and "Prima vencida" not in alerta and "ICA pagado" not in alerta
    assert 'id="alerta-venc"' not in cliente_dueno.get("/hallazgos/").content.decode()


@pytest.mark.django_db
def test_ventana_de_alerta_es_un_parametro(cliente_dueno):
    from datetime import date

    from empresa.models import Parametro

    crear("iva", "lejos", 40, nombre="Obligación a 40 días")
    assert 'id="alerta-venc"' not in cliente_dueno.get("/").content.decode()
    Parametro.objects.create(codigo="ALERTA_PANTALLA_DIAS", descripcion="x", tipo="decimal", valor="45",
                             vigente_desde=date(2025, 1, 1), estado="verificado")
    html = cliente_dueno.get("/").content.decode()
    assert 'id="alerta-venc"' in html and "próximos 45 días" in html


@pytest.mark.django_db
def test_vencida_no_sale_en_la_alerta_pero_si_en_rojo_en_el_calendario(cliente_dueno):
    hoy = timezone.localdate()
    crear("retefuente", "v", -2, nombre="Retención vencida")
    assert 'id="alerta-venc"' not in cliente_dueno.get("/").content.decode()
    html = cliente_dueno.get(f"/calendario/?anio={hoy.year}&mes={hoy.month}").content.decode()
    assert 'class="ob rojo urgente"' in html


@pytest.mark.django_db
def test_sin_pendientes_no_hay_alerta(cliente_dueno):
    crear("retefuente", "x", 2, estado="pagada")
    assert 'id="alerta-venc"' not in cliente_dueno.get("/").content.decode()


@pytest.mark.django_db
def test_colores_en_el_calendario(cliente_dueno):
    hoy = timezone.localdate()
    crear("retefuente", "rojo", -2, nombre="Vencida hace dos días")
    crear("retefuente", "naranja", 3, nombre="Por vencer")
    crear("iva", "verde", 0, estado="pagada", nombre="Pagada hoy")
    html = cliente_dueno.get(f"/calendario/?anio={hoy.year}&mes={hoy.month}").content.decode()
    assert 'class="ob rojo urgente"' in html and 'class="ob naranja urgente"' in html and 'class="ob verde"' in html
    assert "Vencida</span>" in html
    assert "✓ Presentada y pagada" in html


@pytest.mark.django_db
def test_login_profesional(client):
    html = client.get("/ingresar/").content.decode()
    assert "DH Grupo Empresarial" in html and "Creado por" in html
    assert "no reemplaza a World Office" not in html  # el aviso largo ya no estorba en el ingreso
    assert "img/logo-dhstore-claro.png" in html and 'id="ver-clave"' in html
    assert 'autocomplete="username"' in html and 'autocomplete="current-password"' in html


@pytest.mark.django_db
def test_paginas_internas_conservan_el_aviso_y_el_credito(cliente_dueno):
    html = cliente_dueno.get("/hallazgos/").content.decode()
    assert "no reemplaza a World Office" in html and "DH Grupo Empresarial" in html


def test_probar_correo_sin_configurar_falla_claro(settings):
    from django.core.management import call_command
    from django.core.management.base import CommandError

    settings.EMAIL_HOST = ""
    with pytest.raises(CommandError, match="EMAIL_HOST"):
        call_command("probar_correo", "a@ejemplo.com")


@pytest.mark.django_db
def test_probar_correo_envia(settings, mailoutbox):
    from django.core.management import call_command

    settings.EMAIL_HOST = "smtp.ejemplo.com"
    call_command("probar_correo", "a@ejemplo.com")
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["a@ejemplo.com"]


@pytest.mark.django_db
def test_exogena_dian_2025_queda_presentada(datos_iniciales):
    o = Obligacion.objects.get(tipo="exogena", clave="2025")
    assert o.estado == "presentada" and o.semaforo == "verde"
