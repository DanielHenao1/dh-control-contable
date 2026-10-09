from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from empresa.models import Parametro, Usuario

from .historico import solo_vigentes
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
    candidatas = solo_vigentes(Obligacion.objects.filter(
        fecha_limite__isnull=False, fecha_limite__lte=horizonte
    )).exclude(estado__in=["presentada", "pagada"]).exclude(ultima_alerta=hoy)
    salida = []
    for o in candidatas:
        restantes = (o.fecha_limite - hoy).days
        if restantes < 0 or restantes in dias:
            salida.append((o, restantes))
    return salida


COLOR = {"vencida": "#c0392b", "urgente": "#c0392b", "proxima": "#b8780a", "lejana": "#14284b"}


def _cuando(d):
    if d < 0:
        return f"VENCIDA hace {-d} día(s)"
    if d == 0:
        return "Vence HOY"
    return f"Vence en {d} día(s)"


def _fila(o, d):
    color = COLOR["vencida"] if d < 0 else COLOR["urgente"] if d <= 7 else COLOR["proxima"] if d <= 30 else COLOR["lejana"]
    return {"fecha": o.fecha_limite, "nombre": o.nombre, "periodo": o.periodo_texto, "cuando": _cuando(d),
            "estado": o.get_estado_display(), "color": color, "dias": d}


def _texto(filas, titulo):
    lineas = [f"- {f['nombre']} {f['periodo']}: {f['fecha']:%d-%m-%Y} ({f['cuando']}), estado: {f['estado']}" for f in filas]
    return f"{titulo}\n\n" + "\n".join(lineas) + "\n\nFechas calculadas por regla; la DIAN prevalece ante cualquier diferencia."


def enviar_alertas(hoy=None):
    from empresa.correos import enviar_html

    hoy = hoy or timezone.localdate()
    pendientes = obligaciones_a_alertar(hoy)
    para = destinatarios()
    if not pendientes or not para:
        return 0
    filas = sorted((_fila(o, d) for o, d in pendientes), key=lambda f: f["fecha"])
    enviar_html(
        "alerta", "DH Control Contable: vencimientos que requieren atención", "alerta", {"filas": filas}, para,
        _texto(filas, "Obligaciones que requieren atención:"),
    )
    for o, _ in pendientes:
        o.ultima_alerta = hoy
        o.save(update_fields=["ultima_alerta"])
    return len(pendientes)


def destinatarios_resumen():
    return list(settings.RESUMEN_SEMANAL_DESTINATARIOS) or destinatarios()


def datos_resumen(hoy=None):
    """Todo lo pendiente del año en curso, separado en vencido, próximos 30 días y más adelante."""
    hoy = hoy or timezone.localdate()
    del_anio = Obligacion.objects.filter(fecha_limite__year=hoy.year)
    pend = list(del_anio.exclude(estado__in=["presentada", "pagada"]).order_by("fecha_limite"))
    filas = [_fila(o, (o.fecha_limite - hoy).days) for o in pend]
    return {
        "hoy": hoy, "anio": hoy.year,
        "vencidas": [f for f in filas if f["dias"] < 0],
        "proximas": [f for f in filas if 0 <= f["dias"] <= 30],
        "despues": [f for f in filas if f["dias"] > 30],
        "total": del_anio.count(), "cumplidas": del_anio.filter(estado__in=["presentada", "pagada"]).count(),
    }


def enviar_resumen_semanal(hoy=None, para=None):
    from empresa.correos import enviar_html

    datos = datos_resumen(hoy)
    para = para or destinatarios_resumen()
    if not para:
        return 0
    todas = datos["vencidas"] + datos["proximas"] + datos["despues"]
    texto = (
        f"Resumen semanal de pendientes {datos['anio']}: {len(datos['vencidas'])} vencida(s), "
        f"{len(datos['proximas'])} en los próximos 30 días, {datos['cumplidas']} de {datos['total']} cumplidas.\n\n"
        + (_texto(todas, "Pendientes:") if todas else "Todo al día: no hay obligaciones pendientes.")
    )
    enviar_html("resumen", f"DH Control Contable: resumen semanal de pendientes ({datos['hoy']:%d/%m/%Y})", "resumen", datos, para, texto)
    return len(todas)
