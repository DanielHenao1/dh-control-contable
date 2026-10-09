"""Auditoría automática de cambios en modelos de negocio + login/logout."""
from django.apps import apps
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

MODELOS_AUDITADOS = {
    "empresa.Empresa", "empresa.Periodo", "empresa.Parametro", "empresa.PerfilImportacion",
    "empresa.ArchivoCargado", "empresa.Usuario",
    "terceros.Tercero",
    "facturacion.Factura",
    "impuestos.ConceptoRetencion", "impuestos.Declaracion", "impuestos.DiferenciaFiscal",
    "calendario.ReglaVencimiento", "calendario.Obligacion", "calendario.Festivo",
    "controles.Hallazgo",
    "analitica.Simulacion",
    "contratistas.Contratista", "contratistas.Entrega", "contratistas.InformeContratista",
    "contratistas.Observacion",
}
CAMPOS_SENSIBLES = {"password"}


def _registrar(accion, instancia, **extra):
    from .models import RegistroAuditoria

    RegistroAuditoria.registrar(accion, objeto=instancia, descripcion=str(instancia)[:300], **extra)


def conectar():
    for etiqueta in MODELOS_AUDITADOS:
        try:
            modelo = apps.get_model(etiqueta)
        except LookupError:
            continue
        post_save.connect(_guardado, sender=modelo, dispatch_uid=f"aud-save-{etiqueta}")
        post_delete.connect(_eliminado, sender=modelo, dispatch_uid=f"aud-del-{etiqueta}")


def _guardado(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    _registrar("crear" if created else "modificar", instance)


def _eliminado(sender, instance, **kwargs):
    _registrar("eliminar", instance)


def _ip(request):
    if request is None:
        return None
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")).split(",")[0].strip() or None


@receiver(user_logged_in)
def _login(sender, request, user, **kwargs):
    from .models import RegistroAuditoria

    RegistroAuditoria.registrar("login", usuario=user, descripcion="Ingreso", ip=_ip(request))


@receiver(user_logged_out)
def _logout(sender, request, user, **kwargs):
    from .models import RegistroAuditoria

    if user:
        RegistroAuditoria.registrar("logout", usuario=user, descripcion="Salida", ip=_ip(request))


@receiver(user_login_failed)
def _login_fallido(sender, credentials, request=None, **kwargs):
    from .models import RegistroAuditoria

    RegistroAuditoria.registrar(
        "login_fallido", descripcion=f"Intento fallido: {credentials.get('username', '')}", ip=_ip(request),
        usuario=None,
    )


def auditar_lectura(descripcion):
    """Decorador para vistas que muestran o descargan datos sensibles."""
    from functools import wraps

    def deco(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            from .models import RegistroAuditoria

            respuesta = vista(request, *args, **kwargs)
            RegistroAuditoria.registrar(
                "lectura", descripcion=f"{descripcion} ({request.path})", usuario=request.user, ip=_ip(request)
            )
            return respuesta

        return envoltura

    return deco
