from datetime import date, timedelta

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from calendario.alertas import enviar_alertas, enviar_resumen_semanal
from calendario.models import Obligacion


def _html(msg):
    return next(c for c, t in msg.alternatives if t == "text/html")


def _crear(clave, dias, estado="pendiente", nombre="Retención en la fuente"):
    return Obligacion.objects.create(
        tipo="retefuente", clave=clave, nombre=nombre, periodo_texto=clave,
        fecha_limite=timezone.localdate() + timedelta(days=dias), estado=estado,
    )


def _con_logo(msg):
    cids = [a for a in msg.attachments if a.get("Content-ID") == "<logo>"]
    assert len(cids) == 1 and 'src="cid:logo"' in _html(msg)


@pytest.mark.django_db
def test_resumen_semanal_va_a_los_destinatarios_y_muestra_pendientes(settings, mailoutbox):
    settings.RESUMEN_SEMANAL_DESTINATARIOS = ["ventas2@ejemplo.com", "gerencia@ejemplo.com"]
    settings.CSRF_TRUSTED_ORIGINS = ["https://contabilidad.ejemplo.com"]
    hoy = timezone.localdate()
    _crear("vencida", -3, nombre="Retención vencida")
    _crear("pronto", 5, nombre="IVA pronto")
    _crear("pagada", 2, estado="pagada", nombre="ICA pagada")
    Obligacion.objects.create(tipo="iva", clave="lejos", nombre="Renta lejana", periodo_texto="x",
                              fecha_limite=date(hoy.year, 12, 31), estado="pendiente")
    n = enviar_resumen_semanal()
    assert n >= 3
    m = mailoutbox[0]
    assert m.to == ["ventas2@ejemplo.com", "gerencia@ejemplo.com"]
    html = _html(m)
    assert "RESUMEN SEMANAL" in html and "Retención vencida" in html and "IVA pronto" in html and "Renta lejana" in html
    assert "ICA pagada" not in html and "https://contabilidad.ejemplo.com/calendario/" in html
    assert "1/4" in html  # cumplidas / total del año
    assert "Retención vencida" in m.body  # versión de texto plano
    _con_logo(m)


@pytest.mark.django_db
def test_resumen_sin_pendientes_dice_todo_al_dia(settings, mailoutbox):
    settings.RESUMEN_SEMANAL_DESTINATARIOS = ["a@ejemplo.com"]
    _crear("ok", 3, estado="pagada")
    enviar_resumen_semanal()
    assert "Todo al día" in _html(mailoutbox[0])


@pytest.mark.django_db
def test_resumen_sin_destinatarios_propios_usa_los_de_alertas(settings, mailoutbox):
    settings.RESUMEN_SEMANAL_DESTINATARIOS = []
    settings.ALERTAS_DESTINATARIOS = ["alertas@ejemplo.com"]
    _crear("p", 1)
    enviar_resumen_semanal()
    assert mailoutbox[0].to == ["alertas@ejemplo.com"]


@pytest.mark.django_db
def test_comando_resumen_y_error_sin_destinatarios(settings, mailoutbox):
    from django.core.management.base import CommandError

    settings.RESUMEN_SEMANAL_DESTINATARIOS = []
    settings.ALERTAS_DESTINATARIOS = []
    with pytest.raises(CommandError, match="destinatarios"):
        call_command("enviar_resumen_semanal")
    call_command("enviar_resumen_semanal", "--a", "x@ejemplo.com")
    assert mailoutbox[0].to == ["x@ejemplo.com"]


@pytest.mark.django_db
def test_alerta_de_vencimiento_es_html_con_logo(settings, mailoutbox):
    settings.ALERTAS_DESTINATARIOS = ["a@ejemplo.com"]
    _crear("x", -2, nombre="Retención atrasada")
    assert enviar_alertas() == 1
    m = mailoutbox[0]
    assert "ALERTA DE VENCIMIENTO" in _html(m) and "Retención atrasada" in _html(m) and "VENCIDA hace 2" in _html(m)
    _con_logo(m)


@pytest.mark.django_db
def test_invitacion_y_recuperacion_son_html_con_logo(cliente_dueno, client):
    from empresa.models import Usuario

    cliente_dueno.post("/configuracion/usuario/nuevo/", {"username": "ana", "email": "ana@ejemplo.com", "rol": "asistente"})
    invitacion = mail.outbox[0]
    assert "INVITACIÓN" in _html(invitacion) and "Crear mi contraseña" in _html(invitacion) and "/cuenta/definir-clave/" in _html(invitacion)
    _con_logo(invitacion)
    Usuario.objects.create_user("bea", email="bea@ejemplo.com", password="Clave-segura-2026!")
    client.post("/recuperar/", {"email": "bea@ejemplo.com"})
    rec = mail.outbox[1]
    assert "RECUPERAR CONTRASEÑA" in _html(rec) and "Crear contraseña nueva" in _html(rec) and "/cuenta/definir-clave/" in _html(rec)
    assert "/cuenta/definir-clave/" in rec.body
    _con_logo(rec)


def test_resumen_programado_los_lunes(settings):
    prog = settings.CELERY_BEAT_SCHEDULE["resumen-semanal-pendientes"]
    assert prog["task"] == "calendario.tasks.resumen_semanal_pendientes"
    assert 1 in prog["schedule"].day_of_week and 7 in prog["schedule"].hour
