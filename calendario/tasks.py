from celery import shared_task
from django.utils import timezone

from .alertas import enviar_alertas


@shared_task
def enviar_alertas_vencimiento():
    return enviar_alertas()


@shared_task
def recordar_revision_calendario():
    """En diciembre recuerda comparar el calendario calculado con el oficial de la DIAN."""
    from django.core.mail import send_mail

    from .alertas import destinatarios

    hoy = timezone.localdate()
    if hoy.month != 12 or hoy.day != 1:
        return 0
    para = destinatarios()
    if not para:
        return 0
    send_mail(
        "DH Control Contable: revisar calendario tributario",
        "Es diciembre: compara las fechas calculadas por el sistema con el calendario oficial de la DIAN "
        "del próximo año y ajusta las reglas si hace falta.",
        None, para,
    )
    return 1
