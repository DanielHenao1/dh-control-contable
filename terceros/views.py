from django import forms
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from empresa.auditoria import auditar_lectura
from empresa.permisos import requiere
from reportes.informe import tabla_a_excel

from .models import Tercero


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
    terceros = list(qs[:500])
    if request.GET.get("problemas"):
        terceros = [t for t in terceros if not t.dv_correcto or t.faltantes_exogena()]
    if request.GET.get("exportar") == "xlsx" and request.user.puede("exportar"):
        datos = tabla_a_excel("Terceros", ["NIT", "DV", "DV calculado", "Razón social", "Faltantes exógena"],
                              [(t.nit, t.dv, t.dv_calculado, t.razon_social, ", ".join(t.faltantes_exogena())) for t in terceros])
        r = HttpResponse(datos, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = 'attachment; filename="terceros.xlsx"'
        return r
    return render(request, "terceros/lista.html", {"terceros": terceros, "titulo": "Terceros", "q": q})


@requiere("cargar")
def editar(request, pk):
    t = get_object_or_404(Tercero, pk=pk)
    form = TerceroForm(request.POST or None, instance=t)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tercero actualizado.")
        return redirect("terceros")
    return render(request, "empresa/formulario.html", {"form": form, "titulo": f"Tercero {t.nit}"})
