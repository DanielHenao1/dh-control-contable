"""Obligaciones anteriores a la puesta en marcha del sistema ("histórico").

Lo que venció antes de CONTROL_DESDE no se cuenta como vencido ni genera alertas o hallazgos:
no se sabe su estado real, y su evidencia nunca estuvo en el sistema.
"""
from datetime import date

from empresa.models import Parametro


def control_desde():
    valor = Parametro.obtener_o("CONTROL_DESDE")
    try:
        return date.fromisoformat(valor) if valor else None
    except ValueError:
        return None


def solo_vigentes(queryset):
    """Excluye las obligaciones con fecha límite anterior a CONTROL_DESDE (las sin fecha se conservan)."""
    from django.db.models import Q

    desde = control_desde()
    if desde is None:
        return queryset
    return queryset.filter(Q(fecha_limite__isnull=True) | Q(fecha_limite__gte=desde))
