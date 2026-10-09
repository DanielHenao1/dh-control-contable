from django.urls import path

from . import views

urlpatterns = [
    path("asistente/", views.chat, name="asistente"),
    path("asistente/preguntar/", views.preguntar, name="asistente_preguntar"),
    path("asistente/limpiar/", views.limpiar, name="asistente_limpiar"),
]
