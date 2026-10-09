import pytest
from django.test import override_settings
from django_otp.plugins.otp_totp.models import TOTPDevice

from empresa.models import RegistroAuditoria, Usuario

from .conftest import usuario_con_rol

URLS_GET = ["/", "/hallazgos/", "/terceros/", "/facturas/", "/iva-retencion/", "/conciliaciones/", "/fiscal/",
            "/fiscal/conceptos/", "/proyeccion/", "/simulador/", "/analisis/", "/calendario/", "/calendario/?vista=lista",
            "/calendario/reglas/", "/informes/", "/contratista/", "/cargas/", "/cargas/nueva/", "/configuracion/",
            "/auditoria/", "/perfiles/", "/hallazgos/catalogo/"]


@pytest.mark.django_db
def test_requiere_login(client):
    r = client.get("/")
    assert r.status_code == 302 and "/ingresar/" in r.url


@pytest.mark.django_db
@pytest.mark.parametrize("url", URLS_GET)
def test_pantallas_del_dueno(cliente_dueno, datos_iniciales, url):
    r = cliente_dueno.get(url)
    assert r.status_code == 200, url


@pytest.mark.django_db
def test_roles(client, datos_iniciales):
    consulta = usuario_con_rol("consulta")
    client.force_login(consulta)
    assert client.get("/hallazgos/").status_code == 200
    assert client.get("/cargas/").status_code == 403
    assert client.get("/iva-retencion/").status_code == 403
    assert client.get("/configuracion/").status_code == 403
    client.logout()
    c = usuario_con_rol("contratista")
    client.force_login(c)
    assert client.get("/contratista/").status_code == 200
    assert client.get("/hallazgos/").status_code == 403
    assert client.get("/", follow=False).url == "/contratista/"
    client.logout()
    a = usuario_con_rol("asistente")
    client.force_login(a)
    assert client.get("/cargas/").status_code == 200
    assert client.get("/fiscal/").status_code == 403
    assert client.get("/auditoria/").status_code == 403


@pytest.mark.django_db
def test_contador_solo_lectura(client, datos_iniciales):
    client.force_login(usuario_con_rol("contador"))
    assert client.get("/fiscal/").status_code == 200
    assert client.get("/cargas/nueva/").status_code == 403
    assert client.get("/configuracion/").status_code == 403


@pytest.mark.django_db
@override_settings(OTP_OBLIGATORIO=True)
def test_doble_factor_obligatorio(client, dueno):
    client.force_login(dueno)
    r = client.get("/")
    assert r.status_code == 302 and r.url.endswith("/2fa/configurar/")
    r = client.get("/2fa/configurar/")
    assert r.status_code == 200 and b"<svg" in r.content
    dispositivo = TOTPDevice.objects.get(user=dueno)
    from django_otp.oath import TOTP

    t = TOTP(dispositivo.bin_key, dispositivo.step, dispositivo.t0, dispositivo.digits, dispositivo.drift)
    t.time = __import__("time").time()
    r = client.post("/2fa/configurar/", {"token": f"{t.token():06d}"})
    assert r.status_code == 200 and "recuperación" in r.content.decode()
    assert client.get("/hallazgos/").status_code == 200  # ya verificado


@pytest.mark.django_db
@override_settings(OTP_OBLIGATORIO=True)
def test_codigo_incorrecto_no_pasa(client, dueno):
    TOTPDevice.objects.create(user=dueno, name="p", confirmed=True)
    client.force_login(dueno)
    r = client.post("/2fa/verificar/", {"token": "000000"})
    assert r.status_code == 200
    assert client.get("/").status_code == 302


@pytest.mark.django_db
def test_bloqueo_por_intentos(client, dueno, settings):
    settings.LOGIN_INTENTOS_MAX = 3
    from django.core.cache import cache

    cache.clear()
    for _ in range(3):
        client.post("/ingresar/", {"username": "dueno", "password": "mala"})
    r = client.post("/ingresar/", {"username": "dueno", "password": "Clave-segura-123"})
    assert b"Demasiados intentos" in r.content
    assert RegistroAuditoria.objects.filter(accion="login_fallido").count() >= 3


@pytest.mark.django_db
def test_auditoria_solo_inserta(dueno):
    from datetime import date

    from empresa.models import Parametro

    p = Parametro.objects.create(codigo="X", valor="1", vigente_desde=date(2026, 1, 1))
    r = RegistroAuditoria.objects.filter(modelo="empresa.Parametro", objeto_id=str(p.pk)).first()
    assert r and r.accion == "crear"
    with pytest.raises(ValueError):
        r.save()
    with pytest.raises(ValueError):
        r.delete()


@pytest.mark.django_db
def test_lecturas_sensibles_se_auditan(cliente_dueno, datos_iniciales):
    cliente_dueno.get("/terceros/")
    assert RegistroAuditoria.objects.filter(accion="lectura", descripcion__contains="terceros").exists()


@pytest.mark.django_db
def test_cierre_de_periodo_se_audita(cliente_dueno, datos_iniciales):
    from empresa.models import Periodo

    p = Periodo.obtener(2026, 8)
    cliente_dueno.post(f"/configuracion/periodo/{p.pk}/estado/", {"estado": "cerrado"})
    p.refresh_from_db()
    assert p.cerrado and RegistroAuditoria.objects.filter(accion="cierre").exists()


@pytest.mark.django_db
def test_nuevo_usuario_con_rol(cliente_dueno):
    r = cliente_dueno.post("/configuracion/usuario/nuevo/", {
        "username": "ana", "first_name": "Ana", "last_name": "P", "email": "a@x.co", "rol": "asistente",
        "password1": "Una-clave-larga-987", "password2": "Una-clave-larga-987"})
    assert r.status_code == 302 and Usuario.objects.get(username="ana").rol == "asistente"


def test_hallazgo_explica_que_hacer_y_a_donde_ir(cliente_dueno, db):
    from controles.models import Hallazgo, ReglaControl
    from empresa.models import Periodo

    p = Periodo.obtener(2026, 10)
    r = ReglaControl.objects.create(codigo="CAL002", nombre="Obligación sin responsable", grupo="calendario", severidad="media")
    h = Hallazgo.objects.create(regla=r, periodo=p, clave="x", titulo="Retención oct: sin responsable", severidad="media", evidencia={"obligacion_id": 1})
    html = cliente_dueno.get(f"/hallazgos/{h.pk}/").content.decode()
    assert "Qué hacer" in html and "/calendario/obligacion/1/" in html and "Cerrar el hallazgo" in html


def test_parametro_se_guarda_y_se_marca_verificado_con_un_clic(cliente_dueno, db):
    from empresa.models import Parametro

    p = Parametro.objects.create(codigo="PUC_CAJA_BANCOS", descripcion="Caja y bancos", tipo="lista", valor="11",
                                 vigente_desde="2025-01-01", estado="por_verificar")
    datos = {"codigo": p.codigo, "descripcion": p.descripcion, "tipo": "lista", "valor": "1110", "vigente_desde": "2025-01-01",
             "estado": "por_verificar", "fuente": "Confirmado por la contadora"}
    cliente_dueno.post(f"/configuracion/parametro/{p.pk}/", datos)
    p.refresh_from_db()
    assert p.valor == "1110" and p.estado == "por_verificar"  # cambiar el valor no lo verifica
    cliente_dueno.post(f"/configuracion/parametro/{p.pk}/", {**datos, "verificar": "1"})
    p.refresh_from_db()
    assert p.estado == "verificado"


def test_bandeja_muestra_por_defecto_solo_lo_abierto(cliente_dueno, db):
    from controles.models import Hallazgo, ReglaControl
    from empresa.models import Periodo

    p = Periodo.obtener(2026, 9)
    r = ReglaControl.objects.create(codigo="XYZ1", nombre="Regla", grupo="g", severidad="media")
    Hallazgo.objects.create(regla=r, periodo=p, clave="a", titulo="Pendiente uno", severidad="media")
    Hallazgo.objects.create(regla=r, periodo=p, clave="b", titulo="Ya corregido", severidad="media", estado="corregido")
    html = cliente_dueno.get("/hallazgos/?anio=2026&mes=9").content.decode()
    assert "Pendiente uno" in html and "Ya corregido" not in html and "1</strong> abiertos" in html
    assert "Ya corregido" in cliente_dueno.get("/hallazgos/?anio=2026&mes=9&estado=todos").content.decode()


def test_menu_hamburguesa_para_celular(cliente_dueno, db):
    html = cliente_dueno.get("/").content.decode()
    assert 'id="menu-toggle"' in html and 'aria-controls="menu-principal"' in html and 'id="menu-principal"' in html
