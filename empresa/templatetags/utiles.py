from decimal import Decimal

from django import template

register = template.Library()


@register.filter
def get_item(d, k):
    try:
        return d.get(k)
    except AttributeError:
        return None


@register.filter
def pesos(v):
    if v is None or v == "":
        return "—"
    try:
        return f"{Decimal(str(v)):,.0f}".replace(",", ".")
    except Exception:
        return v


@register.filter
def porcentaje(v):
    if v is None:
        return "—"
    return f"{Decimal(str(v)) * 100:.1f}%"


ETIQUETAS = {
    "corte": "Corte (mes hasta el que se calcula)", "ingresos": "Ingresos", "costos_gastos": "Costos y gastos",
    "utilidad_contable": "Utilidad contable", "diferencias_mas": "Diferencias fiscales que suman",
    "diferencias_menos": "Diferencias fiscales que restan", "renta_liquida_estimada": "Renta líquida estimada",
    "tarifa": "Tarifa del impuesto de renta", "impuesto_estimado": "Impuesto estimado",
    "tasa_efectiva": "Tasa efectiva de tributación", "tasa_minima": "Tasa mínima de tributación",
    "diferencias_sin_explicar": "Diferencias sin explicar (cantidad)", "anticipo_referencial": "Anticipo (referencia)",
    "ingresos_bimestre": "Ingresos del bimestre", "tarifa_por_mil": "Tarifa de ICA", "contabilidad": "Según contabilidad",
    "costos": "Costos", "gastos": "Gastos", "utilidad": "Utilidad", "activo_total": "Activo total",
    "pasivo_total": "Pasivo total", "margen_bruto": "Margen bruto (utilidad bruta / ingresos)",
    "margen_neto": "Margen neto (utilidad / ingresos)", "endeudamiento": "Endeudamiento (pasivo / activo)",
    "liquidez": "Liquidez corriente (veces)", "rotacion_cartera_dias": "Rotación de cartera (días)",
    "rotacion_proveedores_dias": "Rotación de proveedores (días)",
}
PORCENTAJES = ("tarifa", "tasa_efectiva", "tasa_minima", "margen_bruto", "margen_neto", "endeudamiento")


def _coma(texto):
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def etiqueta(clave):
    """Nombre legible de un indicador o de un valor calculado (de snake_case a texto)."""
    return ETIQUETAS.get(clave) or str(clave).replace("_", " ").capitalize()


@register.filter
def cifra(v, clave=""):
    """Formatea una cifra según lo que es: pesos con puntos de miles, porcentajes, días, veces o conteos."""
    if v is None or v == "":
        return "—"
    try:
        n = Decimal(str(v))
    except Exception:
        return v
    if clave in PORCENTAJES:
        return _coma(f"{n * 100:,.1f}") + " %"
    if clave == "tarifa_por_mil":
        return _coma(f"{n:,.2f}") + " por mil"
    if clave == "liquidez":
        return _coma(f"{n:,.2f}")
    if clave.endswith("_dias"):
        return _coma(f"{n:,.0f}") + " días"
    if clave == "diferencias_sin_explicar":
        return f"{n:,.0f}"
    texto = _coma(f"{abs(n):,.0f}")
    return f"-$ {texto}" if n < 0 else f"$ {texto}"
