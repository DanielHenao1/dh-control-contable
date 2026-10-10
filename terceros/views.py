from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from empresa.auditoria import auditar_lectura
from empresa.permisos import requiere
from reportes.informe import tabla_a_excel

from .models import Tercero
from .servicios import anios_con_datos, nits_con_movimiento, sin_movimiento


class TerceroForm(forms.ModelForm):
    class Meta:
        model = Tercero
        fields = ["dv", "razon_social", "tipo_persona", "regimen", "es_declarante", "es_autorretenedor",
                  "direccion", "ciudad", "email", "telefono", "ciiu"]


@requiere("ver")
@auditar_lectura("Consulta del maestro de terceros")
def lista(request):
    qs = Tercero.objects.all()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(razon_social__icontains=q) | qs.filter(nit__startswith=q)
    anio = request.GET.get("anio", "")
    con_todo = nits_con_movimiento()
    if anio == "sin_movimiento":
        terceros = [t for t in qs if t.nit not in con_todo]
    elif anio.isdigit():
        del_anio = nits_con_movimiento(int(anio))
        terceros = [t for t in qs if t.nit in del_anio]
    else:
        terceros = list(qs)
    total = len(terceros)
    terceros = terceros[:500]
    if request.GET.get("problemas"):
        terceros = [t for t in terceros if not t.dv_correcto or t.faltantes_exogena()]
    if request.GET.get("exportar") == "xlsx" and request.user.puede("exportar"):
        datos = tabla_a_excel("Terceros", ["NIT", "DV", "DV calculado", "Razón social", "Faltantes exógena"],
                              [(t.nit, t.dv, t.dv_calculado, t.razon_social, ", ".join(t.faltantes_exogena())) for t in terceros])
        r = HttpResponse(datos, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = 'attachment; filename="terceros.xlsx"'
        return r
    for t in terceros:
        t.suelto = t.nit not in con_todo
    return render(request, "terceros/lista.html", {
        "terceros": terceros, "titulo": "Terceros", "q": q, "anio": anio, "anios": anios_con_datos(), "total": total,
        "n_sueltos": sum(1 for t in Tercero.objects.all() if t.nit not in con_todo),
    })


@requiere("administrar")
@require_POST
def eliminar(request, pk):
    """Borra un tercero del maestro. Si todavía tiene movimientos, volverá a crearse al próximo import."""
    from empresa.models import RegistroAuditoria

    t = get_object_or_404(Tercero, pk=pk)
    con_movimiento = t.nit in nits_con_movimiento()
    descripcion = str(t)
    t.delete()
    RegistroAuditoria.registrar("eliminar", descripcion=f"Tercero {descripcion} eliminado del maestro", detalle={"con_movimiento": con_movimiento}, usuario=request.user)
    messages.success(request, f"Tercero {descripcion} eliminado." + (" Aún aparece en archivos cargados: volverá si se importa de nuevo." if con_movimiento else ""))
    return redirect(request.POST.get("volver") or "terceros")


@requiere("administrar")
@require_POST
def limpiar(request):
    """Borra de una vez los terceros que ya no aparecen en ningún archivo vigente (p. ej. tras borrar cargas de prueba)."""
    from empresa.models import RegistroAuditoria

    if not request.POST.get("entiendo"):
        messages.error(request, "Marca la casilla para confirmar que se borran los terceros sin movimiento.")
        return redirect("terceros")
    sueltos = sin_movimiento()
    nits = [t.nit for t in sueltos]
    Tercero.objects.filter(pk__in=[t.pk for t in sueltos]).delete()
    RegistroAuditoria.registrar("eliminar", descripcion=f"{len(nits)} terceros sin movimiento eliminados del maestro", detalle={"nits": nits[:200], "total": len(nits)}, usuario=request.user)
    messages.success(request, f"{len(nits)} tercero(s) sin movimiento eliminados. Quedó en la auditoría.")
    return redirect("terceros")


@requiere("cargar")
def editar(request, pk):
    t = get_object_or_404(Tercero, pk=pk)
    form = TerceroForm(request.POST or None, instance=t)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tercero actualizado.")
        return redirect("terceros")
    return render(request, "empresa/formulario.html", {"form": form, "titulo": f"Tercero {t.nit}"})
