"""Matriz de roles y permisos. Un solo lugar para decidir quién puede qué."""
from functools import wraps

from django.core.exceptions import PermissionDenied

PERMISOS = {
    "dueno": {
        "ver", "ver_fiscal", "cargar", "gestionar_hallazgos", "exportar",
        "administrar", "ver_contratista", "gestionar_contratista", "simular",
    },
    "contador": {
        "ver", "ver_fiscal", "gestionar_hallazgos", "exportar", "ver_contratista", "simular",
    },
    "asistente": {"ver", "cargar"},
    "consulta": {"ver"},
    "contratista": {"ver_contratista"},
}


def tiene_permiso(usuario, permiso):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    return permiso in PERMISOS.get(usuario.rol, set())


def requiere(permiso):
    """Decorador de vistas: exige login y el permiso indicado."""

    def decorador(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login

                return redirect_to_login(request.get_full_path())
            if not tiene_permiso(request.user, permiso):
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
