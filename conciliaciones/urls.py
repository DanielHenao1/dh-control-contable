from django.urls import path

from . import views

urlpatterns = [
    path("iva-retencion/", views.iva_retencion, name="iva_retencion"),
    path("iva/", views.iva, name="iva"),
    path("retencion/", views.retencion, name="retencion"),
    path("conciliaciones/", views.otras, name="conciliaciones"),
]
