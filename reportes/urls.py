from django.urls import path

from . import views

urlpatterns = [
    path("informes/", views.lista, name="informes"),
    path("informes/generar/", views.generar, name="informe_generar"),
    path("informes/pdf/", views.pdf, name="informe_pdf"),
    path("informes/excel/", views.excel, name="informe_excel"),
]
