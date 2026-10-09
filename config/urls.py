from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("empresa.urls")),
    path("", include("controles.urls")),
    path("", include("terceros.urls")),
    path("", include("facturacion.urls")),
    path("", include("conciliaciones.urls")),
    path("", include("impuestos.urls")),
    path("", include("calendario.urls")),
    path("", include("reportes.urls")),
    path("", include("contratistas.urls")),
    path("", include("analitica.urls")),
    path("", include("asistente.urls")),
]
