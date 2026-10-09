from django.http import HttpResponse
from django.shortcuts import render

from conciliaciones.servicios import conciliar_facturas
from empresa.auditoria import auditar_lectura
from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request
from reportes.informe import tabla_a_excel

from .models import facturas_vigentes


@requiere("ver")
@auditar_lectura("Consulta de facturas DIAN")
def lista(request):
    periodo = periodo_desde_request(request)
    from controles.reglas_facturas import hay_auxiliares, indice_documentos, movimientos_de

    facturas = list(facturas_vigentes(periodo))
    if request.GET.get("sentido"):
        facturas = [f for f in facturas if f.sentido == request.GET["sentido"]]
    aux = hay_auxiliares(periodo)
    indice = indice_documentos(periodo) if aux else {}
    filas = [{"f": f, "causada": (bool(movimientos_de(f, indice)) if aux else None)} for f in facturas]
    if request.GET.get("solo_sin_causar"):
        filas = [x for x in filas if x["causada"] is False]
    if request.GET.get("exportar") == "xlsx" and request.user.puede("exportar"):
        datos = tabla_a_excel("Facturas", ["Sentido", "Documento", "Fecha", "Emisor", "Receptor", "Subtotal", "IVA", "Total", "Causada"],
                              [(x["f"].sentido, x["f"].numero_completo, x["f"].fecha, x["f"].nit_emisor, x["f"].nit_receptor,
                                x["f"].subtotal, x["f"].iva, x["f"].total, {True: "sí", False: "no", None: "n/d"}[x["causada"]]) for x in filas])
        r = HttpResponse(datos, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        r["Content-Disposition"] = f'attachment; filename="facturas-{periodo}.xlsx"'
        return r
    ctx = {"filas": filas, "resumen": conciliar_facturas(periodo), "titulo": "Facturas DIAN vs contabilidad", "aux": aux, **contexto_selector(periodo)}
    return render(request, "facturacion/lista.html", ctx)
