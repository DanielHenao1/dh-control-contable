from django.utils import timezone

from .models import Periodo

MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def periodo_desde_request(request):
    """Periodo seleccionado por ?anio=&mes=; por defecto el último con datos o el mes actual."""
    try:
        anio, mes = int(request.GET.get("anio", 0)), int(request.GET.get("mes", 0))
        if 2015 <= anio <= 2100 and 1 <= mes <= 12:
            return Periodo.obtener(anio, mes)
    except ValueError:
        pass
    ultimo = Periodo.objects.filter(archivos__vigente=True).order_by("-anio", "-mes").first()
    if ultimo:
        return ultimo
    hoy = timezone.localdate()
    return Periodo.obtener(hoy.year, hoy.month)


def contexto_selector(periodo):
    hoy = timezone.localdate()
    anios = sorted({hoy.year - 1, hoy.year, hoy.year + 1, periodo.anio} | set(Periodo.objects.values_list("anio", flat=True)))
    return {
        "periodo": periodo, "anios": anios,
        "meses": [(i, MESES[i].capitalize()) for i in range(1, 13)],
        "nombre_mes": MESES[periodo.mes].capitalize(),
    }
