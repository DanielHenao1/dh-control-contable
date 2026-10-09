from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from controles.reglas_exogena import pagos_acumulados, tope
from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request
from terceros.models import Tercero

from .models import ConceptoRetencion, Declaracion, DiferenciaFiscal, TarifaICA
from .reglas.ica import borrador_ica
from .reglas.renta import borrador_renta


class DeclaracionForm(forms.ModelForm):
    class Meta:
        model = Declaracion
        fields = ["tipo", "anio", "indice", "formulario", "valor_declarado", "estado", "elabora", "revisa", "firma", "presentada_el"]
        widgets = {"presentada_el": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class ConceptoForm(forms.ModelForm):
    class Meta:
        model = ConceptoRetencion
        fields = ["codigo", "nombre", "base_minima_uvt", "tarifa_declarante", "tarifa_no_declarante",
                  "vigente_desde", "vigente_hasta", "estado", "fuente"]
        widgets = {"vigente_desde": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "vigente_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


class DiferenciaForm(forms.ModelForm):
    class Meta:
        model = DiferenciaFiscal
        fields = ["anio", "concepto", "tipo", "valor", "soporte", "explicada"]


class TarifaICAForm(forms.ModelForm):
    class Meta:
        model = TarifaICA
        fields = ["ciiu", "descripcion", "tarifa_por_mil", "vigente_desde", "vigente_hasta", "estado", "fuente"]
        widgets = {"vigente_desde": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "vigente_hasta": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


@requiere("ver_fiscal")
def fiscal(request):
    periodo = periodo_desde_request(request)
    renta = borrador_renta(periodo.anio, periodo if periodo.saldos.exists() else None)
    bimestre = (periodo.mes + 1) // 2
    ica = borrador_ica(periodo.anio, bimestre)
    t = tope(periodo.anio)
    pagos = pagos_acumulados(periodo)
    maestro = {x.nit: x for x in Tercero.objects.filter(nit__in=list(pagos))}
    exogena = []
    for nit, total in sorted(pagos.items(), key=lambda kv: -kv[1]):
        ter = maestro.get(nit)
        exogena.append({"nit": nit, "nombre": ter.razon_social if ter else "", "total": total,
                        "reportable": (t is not None and total >= t),
                        "faltantes": ter.faltantes_exogena() if ter else ["no está en el maestro"]})
    ctx = {
        "renta": renta.como_dict(), "ica": ica.como_dict(), "bimestre": bimestre, "tope_exogena": t,
        "exogena": exogena[:100], "diferencias": DiferenciaFiscal.objects.filter(anio=periodo.anio),
        "declaraciones": Declaracion.objects.filter(anio=periodo.anio), "titulo": "Renta, ICA y exógena",
        **contexto_selector(periodo),
    }
    return render(request, "impuestos/fiscal.html", ctx)


def _crud(request, modelo, formulario, titulo, destino, pk=None):
    obj = get_object_or_404(modelo, pk=pk) if pk else None
    form = formulario(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Guardado.")
        return redirect(destino)
    return render(request, "empresa/formulario.html", {"form": form, "titulo": titulo})


@requiere("administrar")
def declaracion_editar(request, pk=None):
    return _crud(request, Declaracion, DeclaracionForm, "Declaración", "fiscal", pk)


@requiere("administrar")
def concepto_editar(request, pk=None):
    return _crud(request, ConceptoRetencion, ConceptoForm, "Concepto de retención", "conceptos", pk)


@requiere("administrar")
def diferencia_editar(request, pk=None):
    return _crud(request, DiferenciaFiscal, DiferenciaForm, "Diferencia contable-fiscal", "fiscal", pk)


@requiere("administrar")
def tarifa_ica_editar(request, pk=None):
    return _crud(request, TarifaICA, TarifaICAForm, "Tarifa de ICA", "conceptos", pk)


@requiere("ver_fiscal")
def conceptos(request):
    return render(request, "impuestos/conceptos.html", {
        "conceptos": ConceptoRetencion.objects.all(), "tarifas_ica": TarifaICA.objects.all(),
        "titulo": "Conceptos de retención y tarifas de ICA",
    })
