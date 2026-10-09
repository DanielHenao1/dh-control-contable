"""Bloqueo de intentos repetidos de ingreso (complementa fail2ban en el servidor)."""
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError


def _clave(username, ip):
    return f"login-fallos:{(username or '').lower()}:{ip}"


class FormularioIngreso(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.request = request

    def _ip(self):
        r = self.request
        if r is None:
            return ""
        return r.META.get("HTTP_X_FORWARDED_FOR", r.META.get("REMOTE_ADDR", "")).split(",")[0].strip()

    def clean(self):
        usuario = self.data.get("username", "")
        clave = _clave(usuario, self._ip())
        if cache.get(clave, 0) >= settings.LOGIN_INTENTOS_MAX:
            raise ValidationError(
                "Demasiados intentos fallidos. Espera unos minutos antes de volver a intentar.",
                code="bloqueado",
            )
        try:
            datos = super().clean()
        except ValidationError:
            cache.set(clave, cache.get(clave, 0) + 1, settings.LOGIN_BLOQUEO_SEGUNDOS)
            raise
        cache.delete(clave)
        return datos
