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
    assert [o.semaforo for o in (pend, futura, pres, pagada)] == ["rojo", "rojo", "ambar", "verde"]
    assert pend.urgente and not futura.urgente and not pres.urgente and not pagada.urgente
    assert pend.dias_restantes == 3 and pagada.dias_restantes == -5


@pytest.mark.django_db
def test_alerta_en_pantalla_solo_en_tablero_y_calendario(cliente_dueno):
    crear("retefuente", "p1", 5)
    crear("iva", "p2", 90, nombre="IVA lejano")
    crear("ica", "ok", 1, estado="pagada", nombre="ICA pagado")
    for url in ("/", "/calendario/"):
        html = cliente_dueno.get(url).content.decode()
        assert 'id="alerta-venc"' in html and 'class="alerta-roja"' in html, url
        alerta = html[html.index('class="alerta-roja"'):html.index("</dialog>")]
        assert "Retención en la fuente" in alerta and "vence en 5 día(s)" in alerta
        assert "IVA lejano" not in alerta and "ICA pagado" not in alerta  # fuera de la ventana o ya pagado
    assert 'id="alerta-venc"' not in cliente_dueno.get("/hallazgos/").content.decode()


@pytest.mark.django_db
def test_vencida_aparece_como_alerta(cliente_dueno):
    crear("retefuente", "v", -2)
    html = cliente_dueno.get("/").content.decode()
    assert "VENCIDA hace 2 día(s)" in html


@pytest.mark.django_db
def test_sin_pendientes_no_hay_alerta(cliente_dueno):
    crear("retefuente", "x", 2, estado="pagada")
    assert 'id="alerta-venc"' not in cliente_dueno.get("/").content.decode()


@pytest.mark.django_db
def test_colores_en_el_calendario(cliente_dueno):
    hoy = timezone.localdate()
    crear("retefuente", "rojo", 0, nombre="Pendiente hoy")
    crear("iva", "verde", 0, estado="pagada", nombre="Pagada hoy")
    html = cliente_dueno.get(f"/calendario/?anio={hoy.year}&mes={hoy.month}").content.decode()
    assert 'class="ob rojo urgente"' in html and 'class="ob verde"' in html
    assert "✓ Presentada y pagada" in html


@pytest.mark.django_db
def test_login_profesional(client):
    html = client.get("/ingresar/").content.decode()
    assert "DH Grupo Empresarial" in html and "Creado por" in html
    assert "no reemplaza a World Office" not in html  # el aviso largo ya no estorba en el ingreso
    assert "img/logo-dhstore.png" in html and 'id="ver-clave"' in html
    assert 'autocomplete="username"' in html and 'autocomplete="current-password"' in html


@pytest.mark.django_db
def test_paginas_internas_conservan_el_aviso_y_el_credito(cliente_dueno):
    html = cliente_dueno.get("/hallazgos/").content.decode()
    assert "no reemplaza a World Office" in html and "DH Grupo Empresarial" in html
