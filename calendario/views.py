import calendar as pycal

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from empresa.cargas import ArchivoDuplicado, registrar_archivo
from empresa.models import Empresa, Periodo
from empresa.permisos import requiere
from empresa.utils import MESES

from .generador import generar_obligaciones
from .historico import solo_vigentes
from .models import Obligacion, ReglaVencimiento


class ObligacionForm(forms.ModelForm):
    evidencia_archivo = forms.FileField(required=False, label="Acuse o evidencia de presentación")

    class Meta:
        model = Obligacion
        fields = ["estado", "elabora", "revisa", "firma", "notas"]


@requiere("ver")
def calendario(request):
    hoy = timezone.localdate()
    try:
        anio, mes = int(request.GET.get("anio", hoy.year)), int(request.GET.get("mes", hoy.month))
    except ValueError:
        anio, mes = hoy.year, hoy.month
    if not (1 <= mes <= 12) or not (2000 <= anio <= 2100):
        anio, mes = hoy.year, hoy.month
    vista = request.GET.get("vista", "mes")
    todas = Obligacion.objects.exclude(fecha_limite=None)
    if vista == "lista":
        obligaciones = Obligacion.objects.filter(fecha_limite__gte=hoy.replace(day=1)).order_by("fecha_limite")[:60]
        sin_fecha = Obligacion.objects.filter(fecha_limite=None)
        return render(request, "calendario/lista.html", {
            "obligaciones": obligaciones, "sin_fecha": sin_fecha, "titulo": "Calendario", "hoy": hoy, "vista": vista,
            "anio": anio, "mes": mes,
        })
    semanas = pycal.Calendar(firstweekday=0).monthdatescalendar(anio, mes)
    por_dia = {}
    for o in todas.filter(fecha_limite__year=anio, fecha_limite__month=mes):
        por_dia.setdefault(o.fecha_limite, []).append(o)
    # Selector desplegable de año y mes: marca cuántas obligaciones siguen pendientes en cada mes del año elegido
    pendientes = {m: 0 for m in range(1, 13)}
    for o in solo_vigentes(Obligacion.objects.filter(fecha_limite__year=anio)).exclude(estado__in=["presentada", "pagada"]):
        pendientes[o.fecha_limite.month] += 1
    meses_panel = [
        {"n": m, "nombre": MESES[m][:3].capitalize(), "pendientes": pendientes[m], "actual": m == mes}
        for m in range(1, 13)
    ]
    anios = list(range(min(hoy.year - 1, anio), max(hoy.year + 3, anio) + 1))
    sig = (anio + (mes == 12), 1 if mes == 12 else mes + 1)
    ant = (anio - (mes == 1), 12 if mes == 1 else mes - 1)
    return render(request, "calendario/mes.html", {
        "semanas": [[(d, por_dia.get(d, []), d.month == mes) for d in s] for s in semanas],
        "titulo": "Calendario", "anio": anio, "mes": mes, "nombre_mes": MESES[mes].capitalize(),
        "sig": sig, "ant": ant, "hoy": hoy, "vista": vista, "meses_panel": meses_panel, "anios": anios,
    })


@requiere("ver")
def obligacion(request, pk):
    o = get_object_or_404(Obligacion, pk=pk)
    puede = request.user.puede("administrar")
    form = ObligacionForm(request.POST or None, request.FILES or None, instance=o)
    if request.method == "POST" and puede and form.is_valid():
        nueva = form.save(commit=False)
        archivo = form.cleaned_data.get("evidencia_archivo")
        if archivo:
            p = Periodo.obtener(timezone.localdate().year, timezone.localdate().month)
            try:
                nueva.evidencia = registrar_archivo(archivo, "declaracion", p, request.user)
            except ArchivoDuplicado as dup:
                nueva.evidencia = dup.existente
        nueva.save()
        messages.success(request, "Obligación actualizada.")
        return redirect("obligacion", pk=pk)
    return render(request, "calendario/obligacion.html", {"o": o, "form": form, "puede": puede, "titulo": o.nombre})


@requiere("administrar")
@require_POST
def generar(request):
    hoy = timezone.localdate()
    if Empresa.actual() is None:
        messages.error(request, "Configura primero la empresa (NIT).")
        return redirect("calendario")
    n = generar_obligaciones(hoy.year - 1, hoy.year + 1)
    messages.success(request, f"Calendario recalculado por regla: {n} obligación(es) nueva(s).")
    return redirect("calendario")


@requiere("ver")
def reglas(request):
    return render(request, "calendario/reglas.html", {"reglas": ReglaVencimiento.objects.all(), "titulo": "Reglas de vencimiento"})
