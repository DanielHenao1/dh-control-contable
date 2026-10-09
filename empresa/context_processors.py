from datetime import timedelta

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
        # Solo lo que vence en los próximos N días (parámetro ALERTA_PANTALLA_DIAS). Lo ya vencido se ve en rojo
        # en el calendario y en el resumen semanal.
        dias = int(Parametro.obtener_o("ALERTA_PANTALLA_DIAS", 20))
        proximas = list(
            Obligacion.objects.filter(fecha_limite__gte=hoy, fecha_limite__lte=hoy + timedelta(days=dias))
            .exclude(estado__in=["presentada", "pagada"]).order_by("fecha_limite")
        )
        ctx["alertas_pantalla"] = proximas
        ctx["alertas_dias"] = dias
        ctx["hoy_iso"] = hoy.isoformat()
    return ctx
