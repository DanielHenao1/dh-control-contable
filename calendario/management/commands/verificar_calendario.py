from django.core.management.base import BaseCommand

from calendario.models import Obligacion


class Command(BaseCommand):
    help = "Lista las fechas que aún no tienen dos fuentes, para contrastarlas con el calendario oficial (cada diciembre)."

    def handle(self, *args, **kw):
        for o in Obligacion.objects.exclude(verificacion="dos_fuentes").order_by("fecha_limite"):
            self.stdout.write(f"{o.fecha_limite or 'sin fecha':<12} {o.nombre} {o.periodo_texto} [{o.get_verificacion_display()}]")
