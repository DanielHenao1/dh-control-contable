import pytest
from django.core.management import call_command

from empresa.models import Usuario


@pytest.fixture
def datos_iniciales(db):
    call_command("cargar_datos_iniciales", verbosity=0)


@pytest.fixture
def dueno(db):
    return Usuario.objects.create_user("dueno", password="Clave-segura-123", rol="dueno", email="dueno@example.com")


@pytest.fixture
def cliente_dueno(client, dueno):
    client.force_login(dueno)
    return client


def usuario_con_rol(rol):
    return Usuario.objects.create_user(f"u_{rol}", password="Clave-segura-123", rol=rol)
