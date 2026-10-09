from django.core.management.base import BaseCommand

from controles.motor import ejecutar_reglas
from empresa.models import Periodo


class Command(BaseCommand):
    help = "Ejecuta los controles de un periodo (por defecto el más reciente con carga)."

    def add_arguments(self, parser):
        parser.add_argument("--anio", type=int)
        parser.add_argument("--mes", type=int)

    def handle(self, *args, anio=None, mes=None, **kw):
        if anio and mes:
            p = Periodo.obtener(anio, mes)
        else:
            p = Periodo.objects.filter(archivos__vigente=True).order_by("-anio", "-mes").first()
        if not p:
            self.stdout.write("No hay periodos con carga.")
            return
        self.stdout.write(f"{p}: {ejecutar_reglas(p)}")
