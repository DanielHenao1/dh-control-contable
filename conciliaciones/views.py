from django.shortcuts import redirect, render
from django.urls import reverse

from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request
from impuestos.reglas.iva import tramo_de

from . import servicios


@requiere("ver_fiscal")
def iva_retencion(request):
    """Ruta anterior: la pantalla se separó en IVA y Retención en la fuente."""
    return redirect(f"{reverse('iva')}?{request.GET.urlencode()}" if request.GET else reverse("iva"))


@requiere("ver_fiscal")
def iva(request):
    periodo = periodo_desde_request(request)
    indice, _, _ = tramo_de(periodo.anio, periodo.mes)
    ctx = {"iva": servicios.conciliar_iva(periodo.anio, indice), "indice_iva": indice, "titulo": "IVA", **contexto_selector(periodo)}
    return render(request, "conciliaciones/iva.html", ctx)


@requiere("ver_fiscal")
def retencion(request):
    periodo = periodo_desde_request(request)
    ctx = {"retencion": servicios.conciliar_retencion(periodo), "titulo": "Retención en la fuente", **contexto_selector(periodo)}
    return render(request, "conciliaciones/retencion.html", ctx)


@requiere("ver_fiscal")
def otras(request):
    periodo = periodo_desde_request(request)
    cuenta_banco = request.GET.get("banco", "").strip()
    bancos = servicios.cuentas_de_banco(periodo)
    if not cuenta_banco and bancos:  # por defecto, la cuenta de banco (1110…) con más movimientos
        candidatas = [c for c in bancos if c["codigo"].startswith("1110")] or bancos
        cuenta_banco = max(candidatas, key=lambda c: c["movimientos"])["codigo"]
    ctx = {
        "aux_balance": servicios.conciliar_auxiliares_vs_balance(periodo),
        "cartera": servicios.conciliar_terceros(periodo, ["13"], 1),
        "proveedores": servicios.conciliar_terceros(periodo, ["22"], -1),
        "banco": servicios.conciliar_banco(periodo, cuenta_banco) if cuenta_banco else None,
        "cuenta_banco": cuenta_banco, "bancos": bancos, "titulo": "Conciliaciones", **contexto_selector(periodo),
    }
    return render(request, "conciliaciones/otras.html", ctx)
