"""Días hábiles y festivos de Colombia (Ley 51 de 1983 'Emiliani' + Semana Santa)."""
from datetime import date, timedelta

from .models import Festivo


def pascua(anio):
    """Domingo de Pascua (algoritmo gregoriano anónimo de Meeus/Jones/Butcher)."""
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    mes, dia = divmod(h + ell - 7 * m + 114, 31)
    return date(anio, mes, dia + 1)


def al_lunes(fecha):
    """Traslada al lunes siguiente (si ya es lunes, se queda)."""
    return fecha + timedelta(days=(7 - fecha.weekday()) % 7)


def festivos_calculados(anio):
    p = pascua(anio)
    fijos = [
        (date(anio, 1, 1), "Año Nuevo"),
        (date(anio, 5, 1), "Día del Trabajo"),
        (date(anio, 7, 20), "Grito de Independencia"),
        (date(anio, 8, 7), "Batalla de Boyacá"),
        (date(anio, 12, 8), "Inmaculada Concepción"),
        (date(anio, 12, 25), "Navidad"),
        (p - timedelta(days=3), "Jueves Santo"),
        (p - timedelta(days=2), "Viernes Santo"),
    ]
    trasladados = [
        (date(anio, 1, 6), "Reyes Magos"),
        (date(anio, 3, 19), "San José"),
        (date(anio, 6, 29), "San Pedro y San Pablo"),
        (date(anio, 8, 15), "Asunción de la Virgen"),
        (date(anio, 10, 12), "Día de la Raza"),
        (date(anio, 11, 1), "Todos los Santos"),
        (date(anio, 11, 11), "Independencia de Cartagena"),
        (p + timedelta(days=39), "Ascensión del Señor"),
        (p + timedelta(days=60), "Corpus Christi"),
        (p + timedelta(days=68), "Sagrado Corazón"),
    ]
    resultado = fijos + [(al_lunes(f), n) for f, n in trasladados]
    return sorted(resultado)


def asegurar_festivos(anio):
    """Crea los festivos calculados del año si la tabla no tiene ninguno para ese año."""
    if Festivo.objects.filter(fecha__year=anio).exists():
        return 0
    Festivo.objects.bulk_create(
        [Festivo(fecha=f, nombre=n, origen="calculado") for f, n in festivos_calculados(anio)],
        ignore_conflicts=True,
    )
    return len(festivos_calculados(anio))


def es_habil(fecha, festivos):
    return fecha.weekday() < 5 and fecha not in festivos


def dia_habil_n(anio, mes, n):
    """Fecha del n-ésimo día hábil del mes (lunes a viernes, sin festivos de la tabla)."""
    asegurar_festivos(anio)
    festivos = set(Festivo.objects.filter(fecha__year=anio).values_list("fecha", flat=True))
    dia = date(anio, mes, 1)
    contados = 0
    while True:
        if es_habil(dia, festivos):
            contados += 1
            if contados == n:
                return dia
        dia += timedelta(days=1)
