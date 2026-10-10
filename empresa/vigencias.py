"""Vigencias anuales de los parámetros que cambian cada año (UVT, topes de exógena, anticipo de renta…).

Cada año el sistema crea la fila del año nuevo con vigencia del 1 de enero, cierra la anterior el 31 de diciembre y
la deja «por verificar»: la UVT y los topes de un año no se heredan (quedan vacíos hasta cargar el valor oficial), y los
valores que suelen mantenerse (tarifas, umbrales) se copian pero siguen pendientes de confirmar. Los cálculos de cada año
toman el valor que estaba vigente en su fecha, así que los de años pasados no cambian.
"""
from datetime import date

from .models import Parametro, RegistroAuditoria

# "vacio": el valor cambia cada año y no se hereda. "copiar": se hereda como punto de partida, por verificar.
POLITICAS = {
    "UVT": "vacio",
    "EXOGENA_TOPE_PESOS": "vacio",
    "EXOGENA_TOPE_UVT": "vacio",
    "EXOGENA_DIAN_UMBRAL_UVT": "vacio",
    "EXOGENA_DISTRITAL_UMBRAL_UVT": "copiar",
    "RENTA_ANTICIPO_PORCENTAJE": "vacio",
    "PUC_PASIVO_FINANCIERO_CORRIENTE": "vacio",
    "RENTA_TARIFA": "copiar",
    "RENTA_TASA_MINIMA": "copiar",
    "IVA_TOPE_BIMESTRAL_UVT": "copiar",
}
PRIMER_ANIO = 2025


def crear_vigencia(codigo, anio, usuario=None):
    """Crea la fila del año para el parámetro si no existe. Devuelve la fila nueva o None."""
    inicio = date(anio, 1, 1)
    vigente = Parametro.vigente(codigo, inicio)
    if vigente is not None and vigente.vigente_desde.year == anio:
        return None  # el año ya tiene su valor
    base = vigente or Parametro.objects.filter(codigo=codigo, vigente_desde__lt=inicio).order_by("-vigente_desde").first()
    if base is None:
        return None
    if vigente is not None and (vigente.vigente_hasta is None or vigente.vigente_hasta >= inicio):
        vigente.vigente_hasta = date(anio - 1, 12, 31)
        vigente.save(update_fields=["vigente_hasta"])
    heredar = POLITICAS.get(codigo) == "copiar"
    nuevo = Parametro.objects.create(
        codigo=codigo, descripcion=base.descripcion, tipo=base.tipo, valor=base.valor if heredar else "",
        vigente_desde=inicio, vigente_hasta=None, estado=Parametro.Estado.POR_VERIFICAR,
        fuente=(f"Vigencia {anio} creada por el sistema; " + ("valor heredado de la anterior: confirmarlo" if heredar else "cargar el valor oficial del año"))[:300],
    )
    RegistroAuditoria.registrar(
        "crear", objeto=nuevo, descripcion=f"Vigencia {anio} de {codigo}", detalle={"heredado": heredar}, usuario=usuario,
    )
    return nuevo


def asegurar_vigencias(hasta_anio=None, usuario=None):
    """Garantiza una fila por año (desde 2025 hasta `hasta_anio`, por defecto el año en curso) en los parámetros anuales."""
    from django.utils import timezone

    hasta = hasta_anio or timezone.localdate().year
    creadas = []
    for codigo in POLITICAS:
        for anio in range(PRIMER_ANIO, hasta + 1):
            nuevo = crear_vigencia(codigo, anio, usuario)
            if nuevo:
                creadas.append(f"{codigo} {anio}")
    return creadas
