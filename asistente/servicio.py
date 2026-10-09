"""Asistente de IA: solo redacta explicaciones y preguntas para el contador a partir de hallazgos ya
calculados. Recibe los datos mínimos (sin NIT, sin nombres) y nunca produce cifras nuevas."""
import json
import re
import urllib.request

from django.conf import settings

from .models import ExplicacionIA

PROMPT_SISTEMA = (
    "Eres un asistente de control contable en Colombia. Recibes UN hallazgo ya calculado por reglas "
    "deterministas. Explícalo en español claro y breve (máximo 120 palabras): qué significa, por qué "
    "importa y 2 preguntas concretas para el contador. NO calcules, NO inventes cifras ni normas, NO des "
    "asesoría tributaria definitiva; usa solo la información recibida y cita la regla si viene incluida. "
    "Si falta información, dilo."
)


def minimizar(texto):
    """Quita identificadores (NIT, correos, números largos) antes de enviar nada fuera del servidor."""
    texto = re.sub(r"\b\d{1,3}(?:\.\d{3}){2,}(?:-\d)?\b", "[NIT]", texto)
    texto = re.sub(r"\b\d{8,12}\b", "[ID]", texto)
    texto = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[correo]", texto)
    return texto


def contenido_minimo(h):
    return {
        "regla": f"{h.regla.codigo} {h.regla.nombre}",
        "norma": h.regla.norma,
        "severidad": h.severidad,
        "titulo": minimizar(h.titulo),
        "detalle": minimizar(h.detalle),
        "cifras": h.cifras,
    }


def explicacion_local(h):
    """Redacción determinista, sin IA: se usa cuando no hay clave de API."""
    partes = [f"{h.titulo}.", h.detalle]
    if h.regla.norma:
        partes.append(f"Regla {h.regla.codigo}: {h.regla.norma}.")
    partes.append(
        "Para el contador: ¿hay un soporte que explique esta diferencia? ¿Se corrige en World Office o se documenta como diferencia aceptada?"
    )
    return " ".join(p for p in partes if p)


def _llamar_api(payload):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        return json.loads(r.read())


def explicar(h, usuario=None):
    """Genera y guarda la explicación de un hallazgo. Sin clave de API usa la redacción local."""
    from empresa.models import RegistroAuditoria

    if not settings.ANTHROPIC_API_KEY:
        texto, modelo = explicacion_local(h), "local"
    else:
        try:
            r = _llamar_api({
                "model": settings.ASISTENTE_MODELO, "max_tokens": 400, "system": PROMPT_SISTEMA,
                "messages": [{"role": "user", "content": json.dumps(contenido_minimo(h), ensure_ascii=False, default=str)}],
            })
            texto = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()
            modelo = settings.ASISTENTE_MODELO
            RegistroAuditoria.registrar("ia", objeto=h, descripcion="Explicación redactada por IA (datos minimizados)", usuario=usuario)
        except Exception:
            texto, modelo = explicacion_local(h), "local (falló la IA)"
    obj, _ = ExplicacionIA.objects.update_or_create(hallazgo=h, defaults={"texto": texto, "modelo": modelo})
    return obj
