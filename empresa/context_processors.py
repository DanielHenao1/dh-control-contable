from django.utils import timezone

from .models import Empresa, Parametro

PAGINAS_CON_ALERTA = ('/', '/calendario/')


def global_(request):
    ctx = {"empresa_actual": None, "parametros_pendientes": 0}
    if not request.user.is_authenticated:
        return ctx
    ctx["empresa_actual"] = Empresa.actual()
    pendientes = 0
    for p in Parametro.objects.all():
        if p.pendiente:
            pendientes += 1
    ctx["parametros_pendientes"] = pendientes
    ctx["permisos"] = {
        k: request.user.puede(k)
        for k in ("ver", "ver_fiscal", "cargar", "gestionar_hallazgos", "administrar", "ver_contratista", "exportar", "simular")
    }
    if request.path in PAGINAS_CON_ALERTA and request.user.puede("ver"):
        from calendario.models import Obligacion

        hoy = timezone.localdate()
        # Todo lo pendiente del año en curso (de enero a diciembre), vencido o por vencer.
        pendientes_anio = list(
            Obligacion.objects.filter(fecha_limite__year=hoy.year)
            .exclude(estado__in=["presentada", "pagada"]).order_by("fecha_limite")
        )
        ctx["alertas_pantalla"] = pendientes_anio
        ctx["alertas_vencidas"] = sum(1 for o in pendientes_anio if o.dias_restantes < 0)
        ctx["alertas_anio"] = hoy.year
        ctx["hoy_iso"] = hoy.isoformat()
    return ctx
