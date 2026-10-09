from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from empresa.correos import enviar_html


class Command(BaseCommand):
    help = "Envía un correo de prueba con la configuración SMTP actual (no muestra la contraseña)."

    def add_arguments(self, parser):
        parser.add_argument("destinatario", help="Correo al que se enviará la prueba")

    def handle(self, *args, destinatario, **opciones):
        if not settings.EMAIL_HOST:
            raise CommandError("EMAIL_HOST está vacío: el correo no está configurado en el .env.")
        modo = "SSL" if settings.EMAIL_USE_SSL else ("STARTTLS" if settings.EMAIL_USE_TLS else "sin cifrado")
        self.stdout.write(
            f"Servidor {settings.EMAIL_HOST}:{settings.EMAIL_PORT} ({modo}), usuario {settings.EMAIL_HOST_USER or '(vacío)'}, "
            f"remitente {settings.DEFAULT_FROM_EMAIL}"
        )
        if settings.EMAIL_PORT == 465 and not settings.EMAIL_USE_SSL:
            self.stdout.write(self.style.WARNING(
                "Aviso: el puerto 465 usa SSL directo. En el .env pon EMAIL_USE_SSL=1 y EMAIL_USE_TLS=0."))
        try:
            enviar_html(
                "prueba", "Prueba de correo · DH Control Contable", "prueba",
                {"servidor": f"{settings.EMAIL_HOST}:{settings.EMAIL_PORT} ({modo})", "remitente": settings.DEFAULT_FROM_EMAIL},
                [destinatario], "Si recibes este mensaje, el envío por SMTP quedó bien configurado.",
            )
        except Exception as e:  # noqa: BLE001 - se muestra el motivo para diagnosticar
            raise CommandError(f"No se pudo enviar: {type(e).__name__}: {e}") from e
        self.stdout.write(self.style.SUCCESS(f"Correo de prueba enviado a {destinatario}."))
