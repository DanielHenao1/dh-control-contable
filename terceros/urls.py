from django.urls import path

from . import views

urlpatterns = [
    path("terceros/", views.lista, name="terceros"),
    path("terceros/<int:pk>/", views.editar, name="tercero_editar"),
]
