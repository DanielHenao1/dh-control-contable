import re

import pytest
from django.core import mail

from empresa.models import RegistroAuditoria, Usuario


def _enlace(cuerpo):
    return re.search(r"https?://\S+/cuenta/definir-clave/\S+/", cuerpo).group(0)


@pytest.mark.django_db
def test_invitacion_envia_correo_y_permite_definir_clave(cliente_dueno, client, settings):
    settings.OTP_OBLIGATORIO = False
    r = cliente_dueno.post("/configuracion/usuario/nuevo/", {
        "username": "carga1", "first_name": "Ana", "last_name": "Pérez", "email": "ana@ejemplo.com", "rol": "asistente"})
    assert r.status_code == 302
    u = Usuario.objects.get(username="carga1")
    assert not u.has_usable_password()
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["ana@ejemplo.com"]
    assert "carga1" in mail.outbox[0].body
    assert RegistroAuditoria.objects.filter(accion="invitacion").exists()

    enlace = _enlace(mail.outbox[0].body)
    ruta = enlace[enlace.index("/cuenta/"):]
    r = client.get(ruta, follow=True)  # Django redirige a la URL con "set-password"
    assert r.status_code == 200 and "Crea tu contraseña" in r.content.decode()
    r = client.post(r.request["PATH_INFO"], {"new_password1": "Clave-segura-2026!", "new_password2": "Clave-segura-2026!"})
    assert r.status_code == 302 and r.url == "/cuenta/clave-lista/"
    u.refresh_from_db()
    assert u.check_password("Clave-segura-2026!")
    assert RegistroAuditoria.objects.filter(accion="clave_definida").exists()
    # el enlace ya no sirve
    assert "Enlace no válido" in client.get(ruta, follow=True).content.decode()


@pytest.mark.django_db
def test_correo_repetido_y_sin_permiso(cliente_dueno):
    Usuario.objects.create_user("x", email="dup@ejemplo.com", password="Clave-segura-2026!")
    r = cliente_dueno.post("/configuracion/usuario/nuevo/", {"username": "y", "email": "DUP@ejemplo.com", "rol": "consulta"})
    assert r.status_code == 200 and "Ya hay un usuario con este correo" in r.content.decode()
    from django.test import Client

    assert Client().get("/configuracion/usuario/nuevo/").status_code == 302  # sin sesión, al ingreso
    otro = Client()
    otro.force_login(Usuario.objects.create_user("c", password="Clave-segura-2026!", rol="consulta"))
    assert otro.get("/configuracion/usuario/nuevo/").status_code in (302, 403)


@pytest.mark.django_db
def test_recuperacion_envia_enlace_sin_revelar_si_existe(client):
    Usuario.objects.create_user("ana", email="ana@ejemplo.com", password="Clave-segura-2026!")
    for correo in ("ana@ejemplo.com", "nadie@ejemplo.com"):
        r = client.post("/recuperar/", {"email": correo})
        assert r.status_code == 302 and r.url == "/recuperar/enviado/"
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ["ana@ejemplo.com"]
    assert "/cuenta/definir-clave/" in mail.outbox[0].body


@pytest.mark.django_db
def test_recuperacion_limita_solicitudes(client):
    from django.core.cache import cache

    cache.clear()
    Usuario.objects.create_user("ana", email="ana@ejemplo.com", password="Clave-segura-2026!")
    for _ in range(8):
        assert client.post("/recuperar/", {"email": "ana@ejemplo.com"}).status_code == 302
    assert len(mail.outbox) == 5


@pytest.mark.django_db
def test_reenviar_invitacion(cliente_dueno):
    u = Usuario.objects.create_user("z", email="z@ejemplo.com")
    u.set_unusable_password()
    u.save()
    r = cliente_dueno.post(f"/configuracion/usuario/{u.pk}/invitar/")
    assert r.status_code == 302 and len(mail.outbox) == 1


def test_login_ofrece_recuperar(client):
    assert "/recuperar/" in client.get("/ingresar/").content.decode()
