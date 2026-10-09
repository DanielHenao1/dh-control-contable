"""Datos que el asistente puede ver: solo lo que el sistema ya calculó, minimizado (sin NIT, correos ni cifras largas
de identificación). Es un resumen de solo lectura: el asistente no consulta la base de datos por su cuenta."""
import json

from django.db.models import Q
from django.utils import timezone

from .servicio import minimizar

MAX_OBLIGACIONES = 80
MAX_HALLAZGOS = 40
MAX_CARGAS = 15
MAX_CARACTERES = 30000


def construir(usuario):
    from calendario.models import Obligacion
    from controles.models import Hallazgo
    from empresa.models import ArchivoCargado, Parametro

    hoy = timezone.localdate()
    obligaciones = [
        {
            "obligacion": f"{o.nombre} {o.periodo_texto}".strip(), "fecha_limite": o.fecha_limite.isoformat() if o.fecha_limite else None,
            "dias_restantes": o.dias_restantes, "estado": o.etiqueta, "laboral": o.laboral,
            "verificacion_de_la_fecha": o.get_verificacion_display(), "fuente": (o.fuente or "")[:160],
        }
        for o in Obligacion.objects.filter(fecha_limite__year=hoy.year).order_by("fecha_limite")[:MAX_OBLIGACIONES]
    ]
    hallazgos = [
        {
            "regla": f"{h.regla.codigo} {h.regla.nombre}", "norma": h.regla.norma, "severidad": h.severidad, "estado": h.estado,
            "periodo": str(h.periodo), "titulo": minimizar(h.titulo), "detalle": minimizar(h.detalle)[:300],
        }
        for h in Hallazgo.objects.filter(estado="abierto").select_related("regla", "periodo").order_by("severidad", "-actualizado")[:MAX_HALLAZGOS]
    ]
    cargas = [
        {"tipo": a.get_tipo_display(), "periodo": str(a.periodo), "estado": a.get_estado_display(), "vigente": a.vigente}
        for a in ArchivoCargado.objects.select_related("periodo").order_by("-creado")[:MAX_CARGAS]
    ]
    parametros = [
        {"codigo": p.codigo, "descripcion": p.descripcion[:120], "valor": p.valor[:60], "estado": p.get_estado_display()}
        for p in Parametro.objects.filter(vigente_desde__lte=hoy).filter(Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=hoy))
    ]
    datos = {
        "fecha_de_hoy": hoy.isoformat(), "obligaciones_del_anio": obligaciones, "hallazgos_abiertos": hallazgos,
        "ultimas_cargas": cargas, "parametros_vigentes": parametros,
    }
    texto = json.dumps(datos, ensure_ascii=False, default=str)
    return texto[:MAX_CARACTERES]
