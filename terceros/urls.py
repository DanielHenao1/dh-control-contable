from django.urls import path

from . import views

urlpatterns = [
    path("terceros/", views.lista, name="terceros"),
    path("terceros/plantilla/", views.plantilla, name="terceros_plantilla"),
    path("terceros/limpiar/", views.limpiar, name="terceros_limpiar"),
    path("terceros/<int:pk>/", views.editar, name="tercero_editar"),
    path("terceros/<int:pk>/eliminar/", views.eliminar, name="tercero_eliminar"),
]
