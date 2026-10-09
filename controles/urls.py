from django.urls import path

from . import views

urlpatterns = [
    path("hallazgos/", views.bandeja, name="hallazgos"),
    path("hallazgos/ejecutar/", views.ejecutar, name="hallazgos_ejecutar"),
    path("hallazgos/catalogo/", views.catalogo, name="catalogo_reglas"),
    path("hallazgos/<int:pk>/", views.detalle, name="hallazgo"),
]
