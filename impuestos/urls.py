from django.urls import path

from . import views

urlpatterns = [
    path("fiscal/", views.fiscal, name="fiscal"),
    path("renta/", views.renta, name="renta"),
    path("ica/", views.ica, name="ica"),
    path("exogena/", views.exogena, name="exogena"),
    path("declaraciones/", views.declaraciones, name="declaraciones"),
    path("fiscal/conceptos/", views.conceptos, name="conceptos"),
    path("fiscal/declaracion/nueva/", views.declaracion_editar, name="declaracion_nueva"),
    path("fiscal/declaracion/<int:pk>/", views.declaracion_editar, name="declaracion_editar"),
    path("fiscal/concepto/nuevo/", views.concepto_editar, name="concepto_nuevo"),
    path("fiscal/concepto/<int:pk>/", views.concepto_editar, name="concepto_editar"),
    path("fiscal/diferencia/nueva/", views.diferencia_editar, name="diferencia_nueva"),
    path("fiscal/diferencia/<int:pk>/", views.diferencia_editar, name="diferencia_editar"),
    path("fiscal/tarifa-ica/nueva/", views.tarifa_ica_editar, name="tarifa_ica_nueva"),
    path("fiscal/tarifa-ica/<int:pk>/", views.tarifa_ica_editar, name="tarifa_ica_editar"),
]
