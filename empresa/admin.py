from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Empresa, Parametro, PerfilImportacion, Periodo, RegistroAuditoria, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Rol", {"fields": ("rol",)}),)
    list_display = ("username", "email", "rol", "is_active")


admin.site.register([Empresa, Parametro, PerfilImportacion, Periodo])


@admin.register(RegistroAuditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario_texto", "accion", "modelo", "descripcion")
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
