from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from empresa.models import Periodo
from empresa.permisos import requiere

from .models import Contratista, Entrega, InformeContratista, Observacion


class EntregaForm(forms.ModelForm):
    anio = forms.IntegerField(min_value=2015, max_value=2100)
    mes = forms.IntegerField(min_value=1, max_value=12)

    class Meta:
        model = Entrega
        fields = ["descripcion", "entregada_el"]
        widgets = {"entregada_el": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class InformeForm(forms.ModelForm):
    class Meta:
        model = InformeContratista
        fields = ["entrega", "recibido_el", "resumen"]
        widgets = {"recibido_el": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ObservacionForm(forms.ModelForm):
    class Meta:
        model = Observacion
        fields = ["informe", "texto"]


@requiere("ver_contratista")
def panel(request):
    contratista = Contratista.objects.first()
    puede = request.user.puede("gestionar_contratista")
    if contratista is None:
        return render(request, "contratistas/panel.html", {"contratista": None, "titulo": "Contratista"})
    hoy = timezone.localdate()
    entregas = list(contratista.entregas.select_related("periodo"))
    ctx = {
        "contratista": contratista, "entregas": entregas, "puede": puede, "titulo": "Contratista",
        "observaciones": contratista.observaciones.all(),
        "form_entrega": EntregaForm(initial={"anio": hoy.year, "mes": hoy.month, "entregada_el": hoy}),
        "form_informe": InformeForm(),
        "form_obs": ObservacionForm(),
        "atrasados": [e for e in entregas if e.informe_atrasado],
    }
    return render(request, "contratistas/panel.html", ctx)


@requiere("gestionar_contratista")
def nueva_entrega(request):
    c = Contratista.objects.first()
    form = EntregaForm(request.POST)
    if c and form.is_valid():
        p = Periodo.obtener(form.cleaned_data["anio"], form.cleaned_data["mes"])
        Entrega.objects.update_or_create(
            contratista=c, periodo=p,
            defaults=dict(descripcion=form.cleaned_data["descripcion"], entregada_el=form.cleaned_data["entregada_el"]),
        )
        messages.success(request, "Entrega registrada.")
    else:
        messages.error(request, "Revisa los datos de la entrega.")
    return redirect("contratista")


@requiere("gestionar_contratista")
def nuevo_informe(request):
    form = InformeForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Informe registrado.")
    else:
        messages.error(request, "Revisa los datos del informe.")
    return redirect("contratista")


@requiere("gestionar_contratista")
def nueva_observacion(request):
    c = Contratista.objects.first()
    form = ObservacionForm(request.POST)
    if c and form.is_valid():
        o = form.save(commit=False)
        o.contratista = c
        o.save()
        messages.success(request, "Observación registrada.")
    return redirect("contratista")


@requiere("ver_contratista")
def responder_observacion(request, pk):
    o = get_object_or_404(Observacion, pk=pk)
    if request.method == "POST":
        o.respuesta = request.POST.get("respuesta", "")
        o.estado = request.POST.get("estado", o.estado) if request.POST.get("estado") in dict(Observacion.Estado.choices) else o.estado
        o.save()
        messages.success(request, "Observación actualizada.")
    return redirect("contratista")
