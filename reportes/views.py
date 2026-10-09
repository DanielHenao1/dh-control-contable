from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from empresa.auditoria import auditar_lectura
from empresa.models import RegistroAuditoria
from empresa.permisos import requiere
from empresa.utils import contexto_selector, periodo_desde_request

from .informe import generar_excel, generar_pdf
from .models import InformeMensual


@requiere("ver_fiscal")
def lista(request):
    periodo = periodo_desde_request(request)
    ctx = {"informes": InformeMensual.objects.select_related("periodo", "usuario")[:30], "titulo": "Informes", **contexto_selector(periodo)}
    return render(request, "reportes/lista.html", ctx)


@requiere("exportar")
@require_POST
def generar(request):
    periodo = periodo_desde_request(request)
    InformeMensual.objects.create(periodo=periodo, usuario=request.user)
    messages.success(request, f"Informe de {periodo} registrado. Descárgalo en PDF o Excel.")
    return redirect(f"/informes/?anio={periodo.anio}&mes={periodo.mes}")


@requiere("exportar")
@auditar_lectura("Descarga de informe PDF")
def pdf(request):
    periodo = periodo_desde_request(request)
    contenido, tipo = generar_pdf(periodo)
    r = HttpResponse(contenido, content_type=tipo)
    ext = "pdf" if tipo == "application/pdf" else "html"
    r["Content-Disposition"] = f'attachment; filename="informe-{periodo}.{ext}"'
    return r


@requiere("exportar")
@auditar_lectura("Descarga de informe Excel")
def excel(request):
    periodo = periodo_desde_request(request)
    r = HttpResponse(generar_excel(periodo), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = f'attachment; filename="informe-{periodo}.xlsx"'
    RegistroAuditoria.registrar("descarga", descripcion=f"Informe Excel {periodo}", usuario=request.user)
    return r
