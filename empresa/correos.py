"""Correos HTML con la identidad de DH (logo incrustado) y versión de texto plano."""
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

LOGO = settings.BASE_DIR / "static" / "img" / "logo-correo.png"

# tipo -> (etiqueta, color de la etiqueta)
TIPOS = {
    "invitacion": ("INVITACIÓN", "#2e8b57"),
    "recuperacion": ("RECUPERAR CONTRASEÑA", "#2f6fbd"),
    "alerta": ("ALERTA DE VENCIMIENTO", "#c0392b"),
    "resumen": ("RESUMEN SEMANAL", "#14284b"),
    "prueba": ("PRUEBA DE CORREO", "#6b7280"),
}


def url_sitio():
    if settings.SITE_URL:
        return settings.SITE_URL.rstrip("/")
    origenes = settings.CSRF_TRUSTED_ORIGINS
    return origenes[0].rstrip("/") if origenes else ""


def enviar_html(tipo, asunto, plantilla, contexto, para, texto):
    """Envía un correo con versión HTML (plantilla `correos/<plantilla>.html`) y texto plano."""
    from .models import Empresa

    etiqueta, color = TIPOS[tipo]
    empresa = Empresa.actual()
    contexto = {
        **contexto, "etiqueta": etiqueta, "color_etiqueta": color, "asunto": asunto,
        "empresa": empresa.razon_social if empresa else "DH Control Contable", "sitio": url_sitio(),
    }
    html = render_to_string(f"correos/{plantilla}.html", contexto)
    msg = EmailMultiAlternatives(asunto, texto, settings.DEFAULT_FROM_EMAIL, list(para))
    msg.attach_alternative(html, "text/html")
    msg.mixed_subtype = "related"
    with open(LOGO, "rb") as f:
        logo = MIMEImage(f.read(), _subtype="png")
    logo.add_header("Content-ID", "<logo>")
    logo.add_header("Content-Disposition", "inline", filename="logo-dh-store.png")
    msg.attach(logo)
    msg.send(fail_silently=False)
