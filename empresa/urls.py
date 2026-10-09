from django.contrib.auth.views import LogoutView
from django.urls import path
from django.views.generic import TemplateView

from . import cuentas, views

urlpatterns = [
    path("ingresar/", views.Ingreso.as_view(), name="login"),
    path("salir/", LogoutView.as_view(), name="logout"),
    path("recuperar/", cuentas.RecuperarClave.as_view(), name="clave_olvidada"),
    path("recuperar/enviado/", TemplateView.as_view(template_name="empresa/clave_enviada.html"), name="clave_enviada"),
    path("cuenta/definir-clave/<uidb64>/<token>/", cuentas.DefinirClave.as_view(), name="clave_definir"),
    path("cuenta/clave-lista/", TemplateView.as_view(template_name="empresa/clave_lista.html"), name="clave_lista"),
    path("salud/", views.salud, name="salud"),
    path("2fa/configurar/", views.configurar_2fa, name="2fa_configurar"),
    path("2fa/verificar/", views.verificar_2fa, name="2fa_verificar"),
    path("cargas/", views.cargas_lista, name="cargas"),
    path("cargas/nueva/", views.cargas_nueva, name="carga_nueva"),
    path("cargas/<int:pk>/", views.carga_detalle, name="carga_detalle"),
    path("cargas/<int:pk>/confirmar/", views.carga_confirmar, name="carga_confirmar"),
    path("cargas/<int:pk>/eliminar/", views.carga_eliminar, name="carga_eliminar"),
    path("cargas/<int:pk>/columnas/", views.carga_columnas, name="carga_columnas"),
    path("cargas/<int:pk>/mapear/", views.carga_mapear, name="carga_mapear"),
    path("perfiles/", views.perfiles_lista, name="perfiles"),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/parametro/nuevo/", views.parametro_editar, name="parametro_nuevo"),
    path("configuracion/parametro/<int:pk>/", views.parametro_editar, name="parametro_editar"),
    path("configuracion/usuario/nuevo/", views.usuario_nuevo, name="usuario_nuevo"),
    path("configuracion/usuario/<int:pk>/invitar/", views.usuario_invitar, name="usuario_invitar"),
    path("configuracion/periodo/<int:pk>/estado/", views.periodo_estado, name="periodo_estado"),
    path("auditoria/", views.auditoria, name="auditoria"),
]
