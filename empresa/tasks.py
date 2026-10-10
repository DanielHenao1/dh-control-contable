from celery import shared_task

from .vigencias import asegurar_vigencias


@shared_task
def asegurar_vigencias_anuales():
    """Cada día revisa que los parámetros anuales tengan su fila del año en curso (el 1 de enero crea las nuevas)."""
    return asegurar_vigencias()
