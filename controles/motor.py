"""Motor de reglas: cada regla es una función determinista que devuelve hallazgos.

La IA no interviene aquí. Un hallazgo se identifica por (regla, periodo, clave), así que ejecutar
las reglas varias veces no duplica nada, y los hallazgos que ya no se detectan pasan a 'corregido'.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from empresa.models import Periodo

from .models import Hallazgo, ReglaControl

REGISTRO = {}


@dataclass
class Resultado:
    clave: str
    titulo: str
    detalle: str = ""
    cifras: dict = field(default_factory=dict)
    evidencia: dict = field(default_factory=dict)
    severidad: str = ""  # vacío = la de la regla


def regla(codigo, grupo, nombre, severidad="media", norma="", descripcion=""):
    def deco(funcion):
        REGISTRO[codigo] = {
            "funcion": funcion, "grupo": grupo, "nombre": nombre, "severidad": severidad,
            "norma": norma, "descripcion": descripcion or (funcion.__doc__ or "").strip(),
        }
        return funcion

    return deco


def cargar_reglas():
    """Importa los módulos de reglas para que se registren."""
    from . import (  # noqa: F401  # noqa: F401
        reglas_calendario,
        reglas_exogena,
        reglas_facturas,
        reglas_integridad,
        reglas_iva,
        reglas_renta,
        reglas_retencion,
        reglas_terceros,
    )


def sincronizar_catalogo():
    cargar_reglas()
    for codigo, r in REGISTRO.items():
        obj, creada = ReglaControl.objects.get_or_create(
            codigo=codigo,
            defaults=dict(grupo=r["grupo"], nombre=r["nombre"], severidad=r["severidad"],
                          norma=r["norma"], descripcion=r["descripcion"]),
        )
        if not creada:
            cambios = {}
            for campo in ("grupo", "nombre", "norma", "descripcion"):
                if getattr(obj, campo) != r[campo]:
                    cambios[campo] = r[campo]
            if cambios:
                for k, v in cambios.items():
                    setattr(obj, k, v)
                obj.save(update_fields=list(cambios))


def _limpio(valor):
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dict):
        return {k: _limpio(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpio(v) for v in valor]
    return valor


@transaction.atomic
def ejecutar_reglas(periodo: Periodo, codigos=None):
    """Ejecuta las reglas activas para el periodo. Devuelve un resumen."""
    sincronizar_catalogo()
    if periodo.cerrado:
        return {"omitido": "periodo cerrado"}
    resumen = {"nuevos": 0, "actualizados": 0, "corregidos": 0, "total": 0}
    for codigo, r in REGISTRO.items():
        if codigos and codigo not in codigos:
            continue
        modelo = ReglaControl.objects.get(codigo=codigo)
        if not modelo.activa:
            continue
        vistos = set()
        resultados = r["funcion"](periodo)
        if resultados is None:  # regla que no aplica a este periodo: no toca lo existente
            continue
        for res in resultados:
            vistos.add(res.clave)
            sev = res.severidad or modelo.severidad
            h, creado = Hallazgo.objects.get_or_create(
                regla=modelo, periodo=periodo, clave=res.clave[:200],
                defaults=dict(titulo=res.titulo[:250], detalle=res.detalle, severidad=sev,
                              cifras=_limpio(res.cifras), evidencia=_limpio(res.evidencia)),
            )
            if creado:
                resumen["nuevos"] += 1
            else:
                h.titulo, h.detalle, h.severidad = res.titulo[:250], res.detalle, sev
                h.cifras, h.evidencia, h.detectado_ultima_vez = _limpio(res.cifras), _limpio(res.evidencia), True
                if h.estado == Hallazgo.Estado.CORREGIDO:
                    h.estado = Hallazgo.Estado.ABIERTO  # reapareció
                h.save()
                resumen["actualizados"] += 1
        # lo que ya no se detecta y seguía abierto, se da por corregido
        pendientes = Hallazgo.objects.filter(regla=modelo, periodo=periodo, estado=Hallazgo.Estado.ABIERTO).exclude(
            clave__in=vistos
        )
        resumen["corregidos"] += pendientes.update(
            estado=Hallazgo.Estado.CORREGIDO, detectado_ultima_vez=False,
            explicacion="Corregido: la regla ya no lo detecta al volver a ejecutarse.",
        )
    resumen["total"] = Hallazgo.objects.filter(periodo=periodo).count()
    return resumen
