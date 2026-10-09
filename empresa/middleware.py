import threading

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

_local = threading.local()


def usuario_actual():
    return getattr(_local, "usuario", None)


def fijar_usuario(usuario):
    _local.usuario = usuario


class UsuarioActualMiddleware:
    """Deja el usuario disponible para la auditoría automática."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        fijar_usuario(request.user if request.user.is_authenticated else None)
        try:
            return self.get_response(request)
        finally:
            fijar_usuario(None)


class RequerirDobleFactorMiddleware:
    """Un usuario autenticado sin verificar su segundo factor solo puede ver las pantallas de 2FA."""

    LIBRES = ("/ingresar/", "/salir/", "/2fa/", "/static/", "/salud/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            settings.OTP_OBLIGATORIO
            and request.user.is_authenticated
            and not request.user.is_verified()
            and not request.path.startswith(self.LIBRES)
        ):
            from django_otp import devices_for_user

            tiene = any(devices_for_user(request.user, confirmed=True))
            return redirect(reverse("2fa_verificar" if tiene else "2fa_configurar"))
        return self.get_response(request)
