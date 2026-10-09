from django.urls import path

from . import views

urlpatterns = [
    path("calendario/", views.calendario, name="calendario"),
    path("calendario/generar/", views.generar, name="calendario_generar"),
    path("calendario/reglas/", views.reglas, name="calendario_reglas"),
    path("calendario/obligacion/<int:pk>/", views.obligacion, name="obligacion"),
]
