from django.core.management.base import BaseCommand

from calendario.dias_habiles import asegurar_festivos


class Command(BaseCommand):
    help = "Genera los festivos de Colombia (Ley 51/1983 y Semana Santa) para un rango de años."

    def add_arguments(self, parser):
        parser.add_argument("desde", type=int)
        parser.add_argument("hasta", type=int)

    def handle(self, *args, desde, hasta, **kw):
        for a in range(desde, hasta + 1):
            n = asegurar_festivos(a)
            self.stdout.write(f"{a}: {n} festivos creados" if n else f"{a}: ya existían")
