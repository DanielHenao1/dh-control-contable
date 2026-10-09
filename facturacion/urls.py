from django.urls import path

from . import views

urlpatterns = [path("facturas/", views.lista, name="facturas")]
