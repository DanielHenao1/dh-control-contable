from celery import shared_task

from empresa.models import Periodo

from .motor import ejecutar_reglas


@shared_task
def ejecutar_reglas_periodo(periodo_id):
    return ejecutar_reglas(Periodo.objects.get(pk=periodo_id))
