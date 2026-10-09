from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from asistente.servicio import explicar
from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request
from reportes.informe import tabla_a_excel

from .models import Hallazgo, ReglaControl
from .motor import ejecutar_reglas


@requiere("ver")
def bandeja(request):
    periodo = periodo_desde_request(request)
    qs = Hallazgo.objects.filter(periodo=periodo).select_related("regla")
    for campo in ("estado", "severidad"):
        if request.GET.get(campo):
            qs = qs.filter(**{campo: request.GET[campo]})
    if request.GET.get("grupo"):
        qs = qs.filter(regla__grupo=request.GET["grupo"])
    if request.GET.get("q"):
        qs = qs.filter(titulo__icontains=request.GET["q"])
    if request.GET.get("exportar") == "xlsx" and request.user.puede("exportar"):
        datos = tabla_a_excel("Hallazgos", ["Regla", "Severidad", "Estado", "Título", "Detalle", "Explicación"],
                              [(h.regla.codigo, h.severidad, h.estado, h.titulo, h.detalle, h.explicacion) for h in qs])
        r = HttpResponse(datos, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = f'attachment; filename="hallazgos-{periodo}.xlsx"'
        return r
    ctx = {
        "hallazgos": qs, "titulo": "Hallazgos", "grupos": ReglaControl.objects.values_list("grupo", flat=True).distinct().order_by("grupo"),
        "filtros": request.GET, **contexto_selector(periodo),
    }
    return render(request, "controles/bandeja.html", ctx)


@requiere("ver")
def detalle(request, pk):
    h = get_object_or_404(Hallazgo.objects.select_related("regla", "periodo"), pk=pk)
    if request.method == "POST":
        if not request.user.puede("gestionar_hallazgos"):
            return redirect("hallazgo", pk=pk)
        accion = request.POST.get("accion")
        if accion == "estado":
            nuevo = request.POST.get("estado")
            if nuevo in dict(Hallazgo.Estado.choices):
                if nuevo == "explicado" and not request.POST.get("explicacion", "").strip():
                    messages.error(request, "Para marcarlo como explicado, escribe la explicación.")
                else:
                    h.estado, h.explicacion = nuevo, request.POST.get("explicacion", h.explicacion)
                    h.resuelto_por = request.user
                    h.save()
                    messages.success(request, "Hallazgo actualizado.")
        elif accion == "ia":
            explicar(h, request.user)
            messages.success(request, "Explicación redactada.")
        return redirect("hallazgo", pk=pk)
    ia = getattr(h, "explicacion_ia", None)
    return render(request, "controles/detalle.html", {"h": h, "ia": ia, "titulo": h.titulo, "estados": Hallazgo.Estado.choices})


@requiere("cargar")
@require_POST
def ejecutar(request):
    periodo = periodo_desde_request(request)
    r = ejecutar_reglas(periodo)
    messages.success(request, f"Controles ejecutados: {r}")
    return redirect(f"/hallazgos/?anio={periodo.anio}&mes={periodo.mes}")


@requiere("ver")
def catalogo(request):
    from .motor import sincronizar_catalogo

    sincronizar_catalogo()
    return render(request, "controles/catalogo.html", {"reglas": ReglaControl.objects.all(), "titulo": "Catálogo de reglas"})
