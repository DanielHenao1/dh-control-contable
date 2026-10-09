"""Qué hacer con cada hallazgo: texto en lenguaje simple y, si aplica, el enlace a la pantalla donde se corrige."""
from django.urls import reverse

CERRAR = (
    "Cuando ya lo atendiste, ciérralo aquí abajo: «Corregido» si arreglaste la causa (por ejemplo, se cargó el archivo o "
    "se corrigió en World Office), o «Explicado» si el hallazgo es correcto pero tiene una razón (escribe cuál)."
)

TEXTOS = {
    "CAL001": "La obligación está vencida o por vencer. Si ya se presentó o pagó, márcala así en la obligación; si no, hay que presentarla o pagarla.",
    "CAL002": "Falta definir quién elabora, revisa y firma. Abre la obligación y asigna a cada persona o al contratista (por ejemplo, Ideako).",
    "CAL003": "La obligación figura presentada, pero falta el soporte. Abre la obligación y sube el acuse o recibo de presentación.",
    "CAL004": "Cada diciembre se contrasta el calendario con el oficial de la DIAN. Hazlo con el contador y deja constancia.",
    "CAL005": "La fecha de esta obligación no tiene una fuente oficial confirmada. Confírmala con el calendario publicado (o con Ideako) y márcala como verificada en la obligación.",
    "INT004": "Falta cargar el archivo de ese mes (auxiliares o balance de prueba). Súbelo en Cargas; los controles se recalculan al confirmar la carga.",
    "EXO001": "Falta el parámetro del tope de exógena. Créalo en Configuración → Parámetros (EXOGENA_TOPE_PESOS o EXOGENA_TOPE_UVT) con la resolución vigente de la DIAN.",
    "FAC001": "La factura aparece en la DIAN pero no se encontró causada en los auxiliares. Revisa en World Office si está registrada; si falta, pídele a Ideako que la cause. Si ya está registrada, explícalo.",
    "FAC002": "La factura está causada por un valor distinto al de la DIAN. Suele ser una retención que el cliente aplicó o un descuento; revisa la causación en World Office y explícalo si es correcto.",
}


def accion_sugerida(h):
    """(texto, url, etiqueta del botón) para el hallazgo."""
    texto = TEXTOS.get(h.regla.codigo, "Revisa la cifra en World Office. Si es correcta, explica por qué; si no, corrígela y vuelve a cargar el archivo.")
    url = etiqueta = ""
    obligacion = (h.evidencia or {}).get("obligacion_id")
    codigo = h.regla.codigo
    if obligacion and codigo.startswith("CAL"):
        url, etiqueta = reverse("obligacion", args=[obligacion]), "Abrir la obligación"
    elif codigo == "INT004":
        url, etiqueta = f"{reverse('carga_nueva')}", "Ir a cargar archivos"
    elif codigo == "EXO001":
        url, etiqueta = reverse("parametro_nuevo"), "Crear el parámetro"
    elif codigo.startswith("FAC"):
        url, etiqueta = f"{reverse('facturas')}?anio={h.periodo.anio}&mes={h.periodo.mes}", "Ver las facturas del mes"
    return {"texto": texto, "url": url, "etiqueta": etiqueta, "cerrar": CERRAR}
