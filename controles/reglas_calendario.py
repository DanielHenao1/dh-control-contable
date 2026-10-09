from datetime import timedelta

from django.utils import timezone

from calendario.models import Obligacion
from empresa.models import Parametro

from .motor import Resultado, regla


def _es_periodo_actual(periodo):
    hoy = timezone.localdate()
    return periodo.anio == hoy.year and periodo.mes == hoy.month


@regla("CAL001", "calendario", "Obligación próxima a vencer o vencida", "alta",
       "Calendario tributario: Decreto 2229 de 2023 y resoluciones distritales")
def por_vencer(periodo):
    """Obligaciones sin presentar que vencen en 7 días o ya vencieron."""
    if not _es_periodo_actual(periodo):
        return None
    hoy = timezone.localdate()
    salida = []
    for o in Obligacion.objects.filter(fecha_limite__isnull=False, fecha_limite__lte=hoy + timedelta(days=7)).exclude(
        estado__in=["presentada", "pagada"]
    ):
        dias = (o.fecha_limite - hoy).days
        sev = "alta" if dias <= 3 else "media"
        estado = f"vencida hace {-dias} día(s)" if dias < 0 else f"vence en {dias} día(s)"
        salida.append(Resultado(clave=f"{o.tipo}|{o.clave}", titulo=f"{o.nombre} {o.periodo_texto}: {estado}",
                                detalle=f"Fecha límite {o.fecha_limite:%d-%m-%Y}. Estado: {o.get_estado_display()}.",
                                severidad=sev, evidencia={"obligacion_id": o.id}))
    return salida


@regla("CAL002", "calendario", "Obligación sin responsable", "media",
       "Cada declaración registra quién la elabora, revisa y firma")
def sin_responsable(periodo):
    """Obligaciones próximas (60 días) sin elabora/revisa/firma."""
    if not _es_periodo_actual(periodo):
        return None
    hoy = timezone.localdate()
    salida = []
    for o in Obligacion.objects.filter(fecha_limite__isnull=False, fecha_limite__lte=hoy + timedelta(days=60), laboral=False).exclude(
        estado__in=["presentada", "pagada"]
    ):
        faltan = [n for n, v in (("elabora", o.elabora), ("revisa", o.revisa), ("firma", o.firma)) if not v]
        if faltan:
            salida.append(Resultado(clave=f"{o.tipo}|{o.clave}", titulo=f"{o.nombre} {o.periodo_texto}: sin responsable",
                                    detalle=f"Falta definir quién {', '.join(faltan)}.", evidencia={"obligacion_id": o.id}))
    return salida


@regla("CAL003", "calendario", "Presentada sin evidencia", "media", "La presentación debe quedar soportada con el acuse")
def sin_evidencia(periodo):
    """Obligaciones marcadas como presentadas sin archivo de evidencia."""
    if not _es_periodo_actual(periodo):
        return None
    return [
        Resultado(clave=f"{o.tipo}|{o.clave}", titulo=f"{o.nombre} {o.periodo_texto}: sin evidencia de presentación",
                  detalle="Sube el acuse o recibo de presentación.", evidencia={"obligacion_id": o.id})
        for o in Obligacion.objects.filter(estado__in=["presentada", "pagada"], evidencia__isnull=True)
    ]


@regla("CAL004", "calendario", "Revisar el calendario contra el oficial de la DIAN", "media",
       "El sistema calcula fechas por regla; cada diciembre se contrastan con el calendario oficial")
def revision_diciembre(periodo):
    """En diciembre, hasta que se marque el calendario del año siguiente como revisado."""
    if not _es_periodo_actual(periodo) or periodo.mes != 12:
        return None
    sig = periodo.anio + 1
    if Parametro.obtener_o(f"CALENDARIO_REVISADO_{sig}"):
        return []
    return [Resultado(clave=str(sig), titulo=f"Comparar el calendario {sig} con el oficial de la DIAN",
                      detalle=f"Cuando lo hagas, crea el parámetro CALENDARIO_REVISADO_{sig}=si.")]


@regla("CAL005", "calendario", "Fecha sin verificar", "baja", "Fechas estimadas o de una sola fuente deben confirmarse")
def fechas_sin_verificar(periodo):
    """Obligaciones próximas cuya fecha no tiene dos fuentes."""
    if not _es_periodo_actual(periodo):
        return None
    hoy = timezone.localdate()
    return [
        Resultado(clave=f"{o.tipo}|{o.clave}", titulo=f"{o.nombre} {o.periodo_texto}: fecha {o.get_verificacion_display().lower()}",
                  detalle=f"{o.fecha_limite:%d-%m-%Y}" if o.fecha_limite else "Sin fecha publicada; confirmar con Ideako.")
        for o in Obligacion.objects.filter(verificacion__in=["estimada", "no_verificada"]).exclude(estado__in=["presentada", "pagada"])
        if o.fecha_limite is None or o.fecha_limite <= hoy + timedelta(days=90)
    ]
