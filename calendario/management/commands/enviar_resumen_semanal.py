from django.core.management.base import BaseCommand, CommandError

from calendario.alertas import destinatarios_resumen, enviar_resumen_semanal


class Command(BaseCommand):
    help = "Envía ahora el resumen semanal de pendientes (a los destinatarios configurados o a los indicados)."

    def add_arguments(self, parser):
        parser.add_argument("--a", nargs="+", help="Correos de destino (si se omite, los de RESUMEN_SEMANAL_DESTINATARIOS)")

    def handle(self, *args, a=None, **opciones):
        para = a or destinatarios_resumen()
        if not para:
            raise CommandError("No hay destinatarios: define RESUMEN_SEMANAL_DESTINATARIOS en el .env o usa --a correo@ejemplo.com")
        try:
            n = enviar_resumen_semanal(para=para)
        except Exception as e:  # noqa: BLE001
            raise CommandError(f"No se pudo enviar: {type(e).__name__}: {e}") from e
        self.stdout.write(self.style.SUCCESS(f"Resumen enviado a {', '.join(para)} ({n} pendiente(s))."))
