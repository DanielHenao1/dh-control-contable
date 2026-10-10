from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

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
    """Ruta anterior: la pantalla se separó en Renta, ICA, Exógena y Declaraciones."""
    return redirect(f"{reverse('renta')}?{request.GET.urlencode()}" if request.GET else reverse("renta"))


@requiere("ver_fiscal")
def renta(request):
    periodo = periodo_desde_request(request)
    r = borrador_renta(periodo.anio, periodo if periodo.saldos.exists() else None)
    ctx = {"renta": r.como_dict(), "diferencias": DiferenciaFiscal.objects.filter(anio=periodo.anio), "vencimientos": _vencimientos(["renta_c1", "renta_c2"], periodo.anio), "titulo": "Renta", **contexto_selector(periodo)}
    return render(request, "impuestos/renta.html", ctx)


@requiere("ver_fiscal")
def ica(request):
    periodo = periodo_desde_request(request)
    bimestre = (periodo.mes + 1) // 2
    ctx = {"ica": borrador_ica(periodo.anio, bimestre).como_dict(), "bimestre": bimestre, "vencimientos": _vencimientos(["ica"], periodo.anio), "titulo": "ICA", **contexto_selector(periodo)}
    return render(request, "impuestos/ica.html", ctx)


def _vencimientos(tipos, anio):
    """Fechas límite del año de los impuestos dados (el calendario es la fuente)."""
    from calendario.models import Obligacion

    return Obligacion.objects.filter(tipo__in=tipos, fecha_limite__year=anio).order_by("fecha_limite")


@requiere("ver_fiscal")
def reteica(request):
    periodo = periodo_desde_request(request)
    ctx = {"vencimientos": _vencimientos(["reteica"], periodo.anio), "titulo": "ReteICA", **contexto_selector(periodo)}
    return render(request, "impuestos/reteica.html", ctx)


def _obligacion_exogena(periodo, codigo):
    from analitica import anual

    _, total = anual.resultados_por_mes(periodo.anio)
    obligaciones, uvt, aviso_uvt = anual.obligacion_exogena(periodo.anio, total["ingresos"], solo=codigo)
    return obligaciones[0], total, uvt, aviso_uvt


@requiere("ver_fiscal")
def exogena_nacional(request):
    periodo = periodo_desde_request(request)
    obligacion, total, uvt, aviso_uvt = _obligacion_exogena(periodo, "EXOGENA_DIAN_UMBRAL_UVT")
    t = tope(periodo.anio)
    pagos = pagos_acumulados(periodo)
    maestro = {x.nit: x for x in Tercero.objects.filter(nit__in=list(pagos))}
    filas = []
    for nit, total_pagos in sorted(pagos.items(), key=lambda kv: -kv[1]):
        ter = maestro.get(nit)
        filas.append({"nit": nit, "nombre": ter.razon_social if ter else "", "total": total_pagos,
                      "reportable": (t is not None and total_pagos >= t),
                      "faltantes": ter.faltantes_exogena() if ter else ["no está en el maestro"]})
    ctx = {
        "obligacion": obligacion, "total": total, "uvt": uvt, "aviso_uvt": aviso_uvt, "tope_exogena": t, "exogena": filas[:100],
        "vencimientos": _vencimientos(["exogena"], periodo.anio), "titulo": "Exógena nacional (DIAN)", **contexto_selector(periodo),
    }
    return render(request, "impuestos/exogena_nacional.html", ctx)


@requiere("ver_fiscal")
def exogena_distrital(request):
    from analitica import anual

    periodo = periodo_desde_request(request)
    obligacion, total, uvt, aviso_uvt = _obligacion_exogena(periodo, "EXOGENA_DISTRITAL_UMBRAL_UVT")
    pagos = anual.pagos_por_tercero(periodo.anio)
    ctx = {
        "obligacion": obligacion, "total": total, "uvt": uvt, "aviso_uvt": aviso_uvt,
        "pagos": pagos[:150], "total_pagos": len(pagos), "sin_nit": sum(1 for f in pagos if not f["nit"]),
        "vencimientos": _vencimientos(["exogena_distrital"], periodo.anio), "titulo": "Exógena distrital (Bogotá)", **contexto_selector(periodo),
    }
    return render(request, "impuestos/exogena_distrital.html", ctx)


@requiere("ver_fiscal")
def declaraciones(request):
    periodo = periodo_desde_request(request)
    ctx = {"declaraciones": Declaracion.objects.filter(anio=periodo.anio), "titulo": "Declaraciones", **contexto_selector(periodo)}
    return render(request, "impuestos/declaraciones.html", ctx)


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
    return _crud(request, Declaracion, DeclaracionForm, "Declaración", "declaraciones", pk)


@requiere("administrar")
def concepto_editar(request, pk=None):
    return _crud(request, ConceptoRetencion, ConceptoForm, "Concepto de retención", "conceptos", pk)


@requiere("administrar")
def diferencia_editar(request, pk=None):
    return _crud(request, DiferenciaFiscal, DiferenciaForm, "Diferencia contable-fiscal", "renta", pk)


@requiere("administrar")
def tarifa_ica_editar(request, pk=None):
    return _crud(request, TarifaICA, TarifaICAForm, "Tarifa de ICA", "conceptos", pk)


@requiere("ver_fiscal")
def conceptos(request):
    return render(request, "impuestos/conceptos.html", {
        "conceptos": ConceptoRetencion.objects.all(), "tarifas_ica": TarifaICA.objects.all(),
        "titulo": "Conceptos de retención y tarifas de ICA",
    })
