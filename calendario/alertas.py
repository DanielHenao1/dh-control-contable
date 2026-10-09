from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from empresa.models import Parametro, Usuario

from .models import Obligacion


def destinatarios():
    if settings.ALERTAS_DESTINATARIOS:
        return list(settings.ALERTAS_DESTINATARIOS)
    return list(
        Usuario.objects.filter(rol__in=["dueno", "contador"], is_active=True)
        .exclude(email="").values_list("email", flat=True)
    )


def umbrales():
    valor = Parametro.obtener_o("ALERTA_DIAS_ANTES", ["15", "7", "3", "1"])
    return sorted({int(x) for x in valor}, reverse=True)


def obligaciones_a_alertar(hoy=None):
    hoy = hoy or timezone.localdate()
    dias = umbrales()
    horizonte = hoy + timedelta(days=max(dias))
    candidatas = Obligacion.objects.filter(
        fecha_limite__isnull=False, fecha_limite__lte=horizonte
    ).exclude(estado__in=["presentada", "pagada"]).exclude(ultima_alerta=hoy)
    salida = []
    for o in candidatas:
        restantes = (o.fecha_limite - hoy).days
        if restantes < 0 or restantes in dias:
            salida.append((o, restantes))
    return salida


def enviar_alertas(hoy=None):
    hoy = hoy or timezone.localdate()
    pendientes = obligaciones_a_alertar(hoy)
    para = destinatarios()
    if not pendientes or not para:
        return 0
    lineas = []
    for o, d in pendientes:
        if d < 0:
            cuando = f"VENCIDA hace {-d} día(s)"
        elif d == 0:
            cuando = "vence HOY"
        else:
            cuando = f"vence en {d} día(s)"
        lineas.append(f"- {o.nombre} {o.periodo_texto}: {o.fecha_limite:%d-%m-%Y} ({cuando}), estado: {o.get_estado_display()}")
    send_mail(
        "DH Control Contable: vencimientos próximos",
        "Obligaciones que requieren atención:\n\n" + "\n".join(lineas)
        + "\n\nFechas calculadas por regla; la DIAN prevalece ante cualquier diferencia.",
        None, para, fail_silently=False,
    )
    for o, _ in pendientes:
        o.ultima_alerta = hoy
        o.save(update_fields=["ultima_alerta"])
    return len(pendientes)
