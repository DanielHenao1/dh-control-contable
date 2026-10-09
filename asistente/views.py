import json

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from empresa.permisos import requiere

from . import servicio

CLAVE_SESION = "asistente_historial"

SUGERENCIAS = [
    "¿Qué obligaciones están vencidas?",
    "¿Qué vence en los próximos 20 días?",
    "¿Qué hallazgos de severidad alta hay abiertos?",
    "¿Cómo van las cargas del mes?",
    "¿Qué parámetros tributarios faltan por verificar?",
]


@requiere("ver_fiscal")
def chat(request):
    return render(request, "asistente/chat.html", {
        "titulo": "Asistente", "activo": bool(settings.ANTHROPIC_API_KEY), "sugerencias": SUGERENCIAS,
        "historial": request.session.get(CLAVE_SESION, []), "maximo": servicio.MAX_PREGUNTA,
    })


@requiere("ver_fiscal")
@require_POST
def preguntar(request):
    try:
        pregunta = json.loads(request.body or b"{}").get("pregunta", "")
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Solicitud no válida."}, status=400)
    historial = request.session.get(CLAVE_SESION, [])
    try:
        respuesta = servicio.responder(request.user, pregunta, historial)
    except servicio.PreguntaInvalida as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except servicio.AsistenteApagado:
        return JsonResponse({"error": "El asistente está apagado: falta configurar la clave de la IA en el servidor."}, status=503)
    except servicio.LimiteExcedido:
        return JsonResponse({"error": "Llegaste al límite de preguntas por hora. Intenta más tarde."}, status=429)
    except servicio.ErrorConsulta:
        return JsonResponse({"error": "No pude consultar la IA en este momento. Intenta de nuevo en unos minutos."}, status=502)
    historial += [{"role": "user", "content": pregunta.strip()}, {"role": "assistant", "content": respuesta}]
    request.session[CLAVE_SESION] = historial[-servicio.MAX_HISTORIAL:]
    return JsonResponse({"respuesta": respuesta})


@requiere("ver_fiscal")
@require_POST
def limpiar(request):
    request.session.pop(CLAVE_SESION, None)
    return redirect("asistente")
