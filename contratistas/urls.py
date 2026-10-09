from django.urls import path

from . import views

urlpatterns = [
    path("contratista/", views.panel, name="contratista"),
    path("contratista/entrega/", views.nueva_entrega, name="contratista_entrega"),
    path("contratista/informe/", views.nuevo_informe, name="contratista_informe"),
    path("contratista/observacion/", views.nueva_observacion, name="contratista_observacion"),
    path("contratista/observacion/<int:pk>/", views.responder_observacion, name="contratista_responder"),
]
