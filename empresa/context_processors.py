from .models import Empresa, Parametro


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
    return ctx
