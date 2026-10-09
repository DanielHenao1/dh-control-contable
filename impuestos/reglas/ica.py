from datetime import date
from decimal import Decimal

from django.db import models

from empresa.models import Periodo
from impuestos.models import TarifaICA

from .comun import CERO, Calculo, total_clase


def tarifa_ica(ciiu, fecha):
    return (
        TarifaICA.objects.filter(ciiu=ciiu, vigente_desde__lte=fecha)
        .filter(models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha))
        .order_by("-vigente_desde").first()
    )


def borrador_ica(anio, bimestre):
    """ICA del bimestre = ingresos del bimestre × tarifa de la actividad (por mil)."""
    c = Calculo()
    m1, m2 = 2 * bimestre - 1, 2 * bimestre
    p2 = Periodo.objects.filter(anio=anio, mes=m2).first()
    p0 = Periodo.objects.filter(anio=anio, mes=m1 - 1).first() if m1 > 1 else None
    if p2 is None:
        c.advertencias.append("No hay balance cargado del último mes del bimestre.")
        return c
    pref = c.usar("PUC_INGRESOS", defecto=["4"]) or ["4"]
    acumulado_fin = total_clase(p2, pref)
    acumulado_ini = total_clase(p0, pref) if p0 else CERO
    ingresos = acumulado_fin - acumulado_ini
    ciiu = c.usar("ICA_ACTIVIDAD_PRINCIPAL")
    tarifa = tarifa_ica(ciiu, date(anio, m2, 1)) if ciiu else None
    impuesto = None
    if tarifa and tarifa.tarifa_por_mil is not None:
        impuesto = (ingresos * tarifa.tarifa_por_mil / Decimal("1000")).quantize(Decimal("1"))
    else:
        c.advertencias.append("Falta la tarifa de ICA de la actividad principal: cárgala en Configuración > Tarifas ICA.")
    c.valores.update({"ingresos_bimestre": ingresos, "impuesto_estimado": impuesto,
                      "tarifa_por_mil": getattr(tarifa, "tarifa_por_mil", None)})
    c.supuestos += [
        "Todos los ingresos se asignan a la actividad principal; si hay varias actividades, separar por CIIU.",
        "No incluye avisos y tableros, sobretasa bomberil ni retenciones de ICA.",
    ]
    return c
