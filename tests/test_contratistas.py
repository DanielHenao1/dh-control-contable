from datetime import date, timedelta

import pytest
from django.utils import timezone

from contratistas.models import Contratista, Entrega, InformeContratista
from empresa.models import Periodo


@pytest.mark.django_db
def test_contratista_inicial(datos_iniciales):
    c = Contratista.objects.get(contrato="CT-0029-2026")
    assert c.nombre == "Ideako" and c.inicio == date(2026, 10, 8) and c.fin == date(2027, 10, 8)
    assert c.honorarios_mensuales == 500000 and c.honorarios_mas_iva


@pytest.mark.django_db
def test_informe_en_15_dias(datos_iniciales):
    c = Contratista.objects.first()
    p = Periodo.obtener(2026, 9)
    e = Entrega.objects.create(contratista=c, periodo=p, entregada_el=timezone.localdate() - timedelta(days=20))
    assert e.fecha_limite_informe == e.entregada_el + timedelta(days=15)
    assert e.informe_atrasado
    InformeContratista.objects.create(entrega=e, recibido_el=timezone.localdate())
    assert not e.informe_atrasado


@pytest.mark.django_db
def test_flujo_http_del_contratista(cliente_dueno, datos_iniciales):
    r = cliente_dueno.post("/contratista/entrega/", {"anio": 2026, "mes": 9, "entregada_el": "2026-10-10", "descripcion": "Exportes de septiembre"})
    assert r.status_code == 302 and Entrega.objects.count() == 1
    cliente_dueno.post("/contratista/observacion/", {"texto": "Falta el soporte de la retención"})
    from contratistas.models import Observacion

    o = Observacion.objects.get()
    cliente_dueno.post(f"/contratista/observacion/{o.pk}/", {"respuesta": "Enviado", "estado": "respondida"})
    o.refresh_from_db()
    assert o.estado == "respondida"
    assert b"Exportes" in cliente_dueno.get("/contratista/").content
