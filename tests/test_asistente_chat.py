import json
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from asistente import contexto, servicio
from calendario.models import Obligacion
from empresa.models import RegistroAuditoria

from .conftest import usuario_con_rol


@pytest.fixture(autouse=True)
def limpiar_cache():
    cache.clear()


@pytest.fixture
def api(monkeypatch, settings):
    """Simula la API de Claude: guarda lo que se le envía y devuelve una respuesta fija."""
    settings.ANTHROPIC_API_KEY = "clave-de-prueba"
    llamadas = []

    def falsa(payload):
        llamadas.append(payload)
        return {"content": [{"type": "text", "text": "Tienes 1 obligación vencida."}], "usage": {"input_tokens": 10, "output_tokens": 5}}

    monkeypatch.setattr(servicio, "_llamar_api", falsa)
    return llamadas


def _preguntar(cliente, pregunta):
    return cliente.post("/asistente/preguntar/", json.dumps({"pregunta": pregunta}), content_type="application/json")


@pytest.mark.django_db
def test_responde_con_los_datos_del_sistema_y_audita(cliente_dueno, api):
    Obligacion.objects.create(
        tipo="retefuente", clave="x", nombre="Retención en la fuente", periodo_texto="sep 2026",
        fecha_limite=timezone.localdate() + timedelta(days=3), estado="pendiente",
    )
    r = _preguntar(cliente_dueno, "¿Qué vence pronto?")
    assert r.status_code == 200 and r.json()["respuesta"] == "Tienes 1 obligación vencida."
    sistema = api[0]["system"]
    assert "Retención en la fuente sep 2026" in sistema and "NUNCA calcules" in sistema and "<datos>" in sistema
    assert api[0]["messages"][-1] == {"role": "user", "content": "¿Qué vence pronto?"}
    assert RegistroAuditoria.objects.filter(accion="ia_pregunta").exists()


@pytest.mark.django_db
def test_el_contexto_no_lleva_nit_ni_correos(datos_iniciales, dueno):
    from controles.models import Hallazgo, ReglaControl
    from empresa.models import Empresa, Periodo

    regla = ReglaControl.objects.create(codigo="R1", grupo="x", nombre="Regla", norma="Art. 1")
    Hallazgo.objects.create(
        regla=regla, periodo=Periodo.obtener(2026, 9), clave="k", severidad="alta",
        titulo="Factura del NIT 900.123.456-7 sin soporte", detalle="Escribir a pepe@ejemplo.com, cédula 1032456789",
    )
    texto = contexto.construir(dueno)
    assert "900.123.456" not in texto and "pepe@ejemplo.com" not in texto and "1032456789" not in texto
    assert "[NIT]" in texto and "[correo]" in texto
    assert Empresa.actual().nit not in texto  # el NIT de la empresa tampoco sale


@pytest.mark.django_db
def test_la_pregunta_se_minimiza_antes_de_enviarla(cliente_dueno, api):
    _preguntar(cliente_dueno, "¿Qué pasa con 900.123.456-7 y pepe@ejemplo.com?")
    enviado = api[0]["messages"][-1]["content"]
    assert "900.123.456" not in enviado and "pepe@ejemplo.com" not in enviado


@pytest.mark.django_db
def test_historial_en_sesion_y_nueva_conversacion(cliente_dueno, api):
    _preguntar(cliente_dueno, "Primera")
    _preguntar(cliente_dueno, "Segunda")
    assert [m["content"] for m in api[1]["messages"]][:2] == ["Primera", "Tienes 1 obligación vencida."]
    assert "Primera" in cliente_dueno.get("/asistente/").content.decode()
    cliente_dueno.post("/asistente/limpiar/")
    assert "Primera" not in cliente_dueno.get("/asistente/").content.decode()


@pytest.mark.django_db
def test_sin_clave_esta_apagado(cliente_dueno, settings):
    settings.ANTHROPIC_API_KEY = ""
    r = _preguntar(cliente_dueno, "Hola")
    assert r.status_code == 503 and "apagado" in r.json()["error"]
    assert "El asistente está apagado" in cliente_dueno.get("/asistente/").content.decode()


@pytest.mark.django_db
def test_preguntas_invalidas(cliente_dueno, api):
    assert _preguntar(cliente_dueno, "   ").status_code == 400
    assert _preguntar(cliente_dueno, "x" * 501).status_code == 400
    assert cliente_dueno.post("/asistente/preguntar/", "no es json", content_type="application/json").status_code == 400
    assert not api


@pytest.mark.django_db
def test_limite_por_hora(cliente_dueno, api, settings):
    settings.ASISTENTE_PREGUNTAS_POR_HORA = 2
    assert _preguntar(cliente_dueno, "a").status_code == 200
    assert _preguntar(cliente_dueno, "b").status_code == 200
    assert _preguntar(cliente_dueno, "c").status_code == 429
    assert len(api) == 2


@pytest.mark.django_db
def test_falla_de_la_api_no_filtra_detalles(cliente_dueno, api, monkeypatch):
    def rota(payload):
        raise OSError("clave sk-secreta rechazada")

    monkeypatch.setattr(servicio, "_llamar_api", rota)
    r = _preguntar(cliente_dueno, "Hola")
    assert r.status_code == 502 and "sk-secreta" not in r.content.decode()
    assert RegistroAuditoria.objects.filter(accion="ia_error").exists()


@pytest.mark.django_db
def test_solo_roles_con_acceso_fiscal(datos_iniciales, api):
    for rol, esperado in (("contador", 200), ("consulta", 403), ("asistente", 403)):
        c = Client()
        c.force_login(usuario_con_rol(rol))
        assert c.get("/asistente/").status_code == esperado, rol
        assert _preguntar(c, "Hola").status_code == esperado, rol
    assert Client().get("/asistente/").status_code == 302
