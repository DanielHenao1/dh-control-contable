from django.urls import path

from . import views

urlpatterns = [
    path("", views.tablero, name="tablero"),
    path("analisis/", views.analisis, name="analisis"),
    path("proyeccion/", views.proyeccion, name="proyeccion"),
    path("proyeccion/recalcular/", views.recalcular, name="proyeccion_recalcular"),
    path("simulador/", views.simulador, name="simulador"),
]
