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
