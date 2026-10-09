"""Invitación de usuarios y recuperación de contraseña por correo."""
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView
from django.core.cache import cache
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .correos import enviar_html
from .models import RegistroAuditoria, Usuario

RECUPERACION_MAX = 5  # solicitudes por IP y hora
RECUPERACION_SEGUNDOS = 3600


def enlace_definir_clave(request, usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return request.build_absolute_uri(reverse("clave_definir", kwargs={"uidb64": uid, "token": token}))


def enviar_invitacion(request, usuario):
    """Envía el correo con el enlace para crear la contraseña. Lanza la excepción del SMTP si falla."""
    contexto = {
        "usuario": usuario, "enlace": enlace_definir_clave(request, usuario),
        "rol": usuario.get_rol_display(), "dias": settings.PASSWORD_RESET_TIMEOUT // 86400,
    }
    enviar_html(
        "invitacion", "Te invitamos a DH Control Contable: crea tu contraseña", "invitacion", contexto, [usuario.email],
        render_to_string("empresa/correo_invitacion.txt", contexto),
    )
    RegistroAuditoria.registrar("invitacion", objeto=usuario, descripcion=f"Invitación enviada a {usuario.username}", usuario=request.user)


def request_enlace(context):
    return f"{context['protocol']}://{context['domain']}" + reverse("clave_definir", kwargs={"uidb64": context["uid"], "token": context["token"]})


class FormularioRecuperacion(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email, html_email_template_name=None):
        contexto = {**context, "enlace": request_enlace(context)}
        enviar_html(
            "recuperacion", "Recupera tu contraseña · DH Control Contable", "recuperacion", contexto, [to_email],
            render_to_string(email_template_name, context),
        )

    def get_users(self, email):
        # Incluye a quien aún no definió contraseña (invitado): recibe el mismo enlace para activarla.
        return Usuario.objects.filter(email__iexact=email, is_active=True)


def _ip(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip()


class RecuperarClave(PasswordResetView):
    template_name = "empresa/clave_olvidada.html"
    email_template_name = "empresa/correo_recuperacion.txt"
    subject_template_name = "empresa/correo_recuperacion_asunto.txt"
    form_class = FormularioRecuperacion
    success_url = reverse_lazy("clave_enviada")

    def form_valid(self, form):
        clave = f"recuperar:{_ip(self.request)}"
        n = cache.get(clave, 0)
        cache.set(clave, n + 1, RECUPERACION_SEGUNDOS)
        if n >= RECUPERACION_MAX:  # misma respuesta que si hubiera enviado: no se revela nada
            return redirect(self.success_url)
        RegistroAuditoria.registrar("recuperacion", descripcion="Solicitud de recuperación de contraseña", ip=_ip(self.request) or None)
        return super().form_valid(form)


class DefinirClave(PasswordResetConfirmView):
    template_name = "empresa/clave_definir.html"
    success_url = reverse_lazy("clave_lista")
    post_reset_login = False

    def form_valid(self, form):
        respuesta = super().form_valid(form)
        RegistroAuditoria.registrar("clave_definida", objeto=form.user, descripcion=f"{form.user.username} definió su contraseña", usuario=form.user)
        return respuesta
