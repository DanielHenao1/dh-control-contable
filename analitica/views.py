from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from calendario.historico import solo_vigentes
from calendario.models import Obligacion
from controles.models import Hallazgo
from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request
from impuestos.reglas.iva import borrador_iva, iva_facturas, tramo_de
from impuestos.reglas.retencion import borrador_retefuente

from . import estimaciones, servicios
from .models import Estimacion, Simulacion


def _semaforo_hallazgos(abiertos):
    if abiertos.filter(severidad="alta").exists():
        return "rojo"
    return "ambar" if abiertos.filter(severidad="media").exists() else "verde"


def tablero(request):
    """¿Qué está mal este mes? Semáforo, 10 indicadores, vencimientos y gráficos de IVA y retención."""
    if not request.user.is_authenticated:
        from django.contrib.auth.views import redirect_to_login

        return redirect_to_login(request.get_full_path())
    if request.user.rol == "contratista":
        return redirect("contratista")
    if not request.user.puede("ver"):
        raise PermissionDenied
    periodo = periodo_desde_request(request)
    abiertos = Hallazgo.objects.filter(periodo=periodo, estado="abierto")
    ind = servicios.indicadores_mes(periodo)
    actual = ind.get("actual", {}) if ind else {}
    previo = ind.get("anio_anterior", {}) if ind else {}
    hoy = timezone.localdate()
    proxima = Obligacion.objects.filter(fecha_limite__gte=hoy).exclude(estado__in=["presentada", "pagada"]).order_by("fecha_limite").first()
    vencidas = solo_vigentes(Obligacion.objects.filter(fecha_limite__lt=hoy)).exclude(estado__in=["presentada", "pagada"]).count()
    indice_iva, _, _ = tramo_de(periodo.anio, periodo.mes)
    iva = borrador_iva(periodo.anio, indice_iva).valores
    ret = borrador_retefuente(periodo).valores
    ver_fiscal = request.user.puede("ver_fiscal")

    def tarjeta(titulo, valor, enlace, semaforo="", nota="", formato="{:,.0f}"):
        texto = "—" if valor is None else (formato.format(valor) if not isinstance(valor, str) else valor)
        return {"titulo": titulo, "valor": texto, "enlace": enlace, "semaforo": semaforo, "nota": nota}

    q = f"?anio={periodo.anio}&mes={periodo.mes}"
    cambio_ing = None
    if actual.get("ingresos") and previo.get("ingresos"):
        cambio_ing = f"{(actual['ingresos'] / previo['ingresos'] - 1):+.0%} vs año anterior"
    tarjetas = [
        tarjeta("Hallazgos abiertos", abiertos.count(), f"/hallazgos/{q}&estado=abierto", _semaforo_hallazgos(abiertos), formato="{}"),
        tarjeta("De severidad alta", abiertos.filter(severidad="alta").count(), f"/hallazgos/{q}&severidad=alta&estado=abierto",
                "rojo" if abiertos.filter(severidad="alta").exists() else "verde", formato="{}"),
        tarjeta("Ingresos acumulados", actual.get("ingresos"), "/", nota=cambio_ing or ""),
        tarjeta("Utilidad acumulada", actual.get("utilidad"), "/", "rojo" if (actual.get("utilidad") or 0) < 0 else ""),
        tarjeta("Margen neto", actual.get("margen_neto"), "/", formato="{:.1%}"),
        tarjeta("Endeudamiento", actual.get("endeudamiento"), "/", formato="{:.1%}"),
        tarjeta("Liquidez corriente", actual.get("liquidez"), "/", formato="{:.2f}", nota="" if "liquidez" in actual else "Falta PUC_ACTIVO/PASIVO_CORRIENTE"),
        tarjeta("Saldo de IVA del período" if ver_fiscal else "IVA", iva.get("saldo") if ver_fiscal else None, f"/iva-retencion/{q}"),
        tarjeta("Retención del mes", (ret.get("contabilidad") if ret.get("contabilidad") is not None else ret.get("retenido_registrado")) if ver_fiscal else None, f"/iva-retencion/{q}"),
        tarjeta("Próximo vencimiento", f"{proxima.nombre} · {proxima.fecha_limite:%d-%m}" if proxima else None, "/calendario/",
                "rojo" if vencidas else ("ambar" if proxima and (proxima.fecha_limite - hoy).days <= 7 else "verde"),
                nota=f"{vencidas} vencida(s) sin presentar" if vencidas else ""),
    ]
    # Datos para gráficos
    meses_ret, ret_serie, iva_g, iva_d = [], [], [], []
    from empresa.models import Periodo as P

    for m in range(1, 13):
        p = P.objects.filter(anio=periodo.anio, mes=m).first()
        meses_ret.append(m)
        if p and ver_fiscal:
            v = borrador_retefuente(p).valores
            ret_serie.append(float(v.get("contabilidad") if v.get("contabilidad") is not None else v.get("retenido_registrado") or 0))
            g, d, _, _ = iva_facturas(periodo.anio, m, m)
            iva_g.append(float(g))
            iva_d.append(float(d))
        else:
            ret_serie.append(0)
            iva_g.append(0)
            iva_d.append(0)
    ctx = {
        "tarjetas": tarjetas, "semaforo": _semaforo_hallazgos(abiertos), "titulo": "Tablero del mes",
        "grafico": {"meses": meses_ret, "retencion": ret_serie, "iva_generado": iva_g, "iva_descontable": iva_d},
        "advertencias": ind.get("advertencias", []) if ind else [],
        "sin_datos": not ind, **contexto_selector(periodo),
    }
    return render(request, "analitica/tablero.html", ctx)


@requiere("ver")
def analisis(request):
    periodo = periodo_desde_request(request)
    an = servicios.anomalias_periodo(periodo)
    ctx = {"ind": servicios.indicadores_mes(periodo), "anomalias": an, "comparativo": servicios.comparativo_clases(periodo), "titulo": "Indicadores y anomalías", **contexto_selector(periodo)}
    return render(request, "analitica/analisis.html", ctx)


@requiere("ver_fiscal")
def proyeccion(request):
    periodo = periodo_desde_request(request)
    est = Estimacion.objects.filter(anio=periodo.anio, corte=periodo)
    tabla = {}
    for e in est:
        tabla.setdefault(e.impuesto, {})[e.escenario] = e
    ctx = {
        "tabla": tabla, "caja": estimaciones.caja_de_impuestos(periodo) if tabla else None,
        "alertas": estimaciones.alertas_estimacion(periodo) if tabla else [],
        "titulo": "Proyección de impuestos", **contexto_selector(periodo),
    }
    return render(request, "analitica/proyeccion.html", ctx)


@requiere("ver_fiscal")
@require_POST
def recalcular(request):
    periodo = periodo_desde_request(request)
    estimaciones.recalcular(periodo)
    messages.success(request, "Estimaciones recalculadas con los datos más recientes.")
    return redirect(f"/proyeccion/?anio={periodo.anio}&mes={periodo.mes}")


class SimulacionForm(forms.Form):
    nombre = forms.CharField(max_length=150)
    ingresos_adelantar = forms.DecimalField(required=False, label="Ingresos que se facturarían antes del cierre", decimal_places=0)
    ingresos_diferir = forms.DecimalField(required=False, label="Ingresos que se facturarían después del cierre", decimal_places=0)
    gastos_planeados = forms.DecimalField(required=False, label="Gastos planeados", decimal_places=0)
    compra_activos = forms.DecimalField(required=False, label="Compra de activos planeada", decimal_places=0)
    cartera_castigar = forms.DecimalField(required=False, label="Cartera que se castigaría", decimal_places=0)
    provision_cartera = forms.DecimalField(required=False, label="Cartera que se provisionaría", decimal_places=0)
    pagos_pendientes_causar = forms.DecimalField(required=False, label="Pagos pendientes de causar", decimal_places=0)


@requiere("simular")
def simulador(request):
    periodo = periodo_desde_request(request)
    form = SimulacionForm(request.POST or None)
    resultado = None
    if request.method == "POST" and form.is_valid():
        ajustes = {k: str(v or 0) for k, v in form.cleaned_data.items() if k != "nombre"}
        resultado = estimaciones.simular(periodo, ajustes)
        if "error" not in resultado:
            Simulacion.objects.create(
                nombre=form.cleaned_data["nombre"], anio=periodo.anio, corte=periodo, autor=request.user,
                ajustes=ajustes, resultado=_a_json(resultado),
            )
    ctx = {"form": form, "resultado": resultado, "historial": Simulacion.objects.filter(anio=periodo.anio)[:10],
           "titulo": "Simulador de cierre", **contexto_selector(periodo)}
    return render(request, "analitica/simulador.html", ctx)


def _a_json(d):
    import json

    return json.loads(json.dumps(d, default=str))



@requiere("ver_fiscal")
def anual(request):
    """Consolidado de todo un año: cobertura por mes, resultados, comprobación de exógena y pagos por tercero."""
    from django.http import HttpResponse

    from reportes.informe import tabla_a_excel

    from . import anual as servicio

    hoy = timezone.localdate()
    try:
        anio = int(request.GET.get("anio") or hoy.year)
    except ValueError:
        anio = hoy.year
    pagos = servicio.pagos_por_tercero(anio)
    if request.GET.get("exportar") == "xlsx" and request.user.puede("exportar"):
        datos = tabla_a_excel(f"Pagos {anio}", ["NIT", "Tercero", "Pagos del año (costos y gastos)"], [(f["nit"], f["nombre"], f["total"]) for f in pagos])
        r = HttpResponse(datos, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = f'attachment; filename="pagos-por-tercero-{anio}.xlsx"'
        return r
    cobertura = servicio.cobertura(anio)
    meses_resultados, total = servicio.resultados_por_mes(anio)
    obligaciones, uvt, aviso_uvt = servicio.obligacion_exogena(anio, total["ingresos"])
    ctx = {
        "titulo": f"Consolidado {anio}", "anio": anio, "anios": sorted({hoy.year - 2, hoy.year - 1, hoy.year, hoy.year + 1, anio}),
        "cobertura": cobertura, "meses_completos": sum(1 for c in cobertura if c["auxiliar"]),
        "resultados": meses_resultados, "total": total, "obligaciones": obligaciones, "uvt": uvt, "aviso_uvt": aviso_uvt,
        "pagos": pagos[:150], "total_pagos": len(pagos), "sin_nit": sum(1 for f in pagos if not f["nit"]),
    }
    return render(request, "analitica/anual.html", ctx)
