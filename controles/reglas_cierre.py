"""Cierre mensual: depreciación y provisiones laborales (nómina la lleva la empresa; aquí solo se controla)."""
from decimal import Decimal

from contabilidad.models import saldos_vigentes
from impuestos.reglas.comun import Calculo, hojas

from .motor import Resultado, regla


def _suma(saldos, prefijos, campo):
    return sum((getattr(s, campo) for s in saldos if any(s.cuenta.codigo.startswith(p) for p in prefijos)), Decimal("0"))


@regla("CIE001", "cierre", "Activos fijos sin depreciación en el mes", "media",
       "Decreto 2420 de 2015 (NIIF): la depreciación se reconoce cada periodo mientras el activo esté en uso")
def depreciacion(periodo):
    """Hay activos fijos depreciables pero el gasto de depreciación del mes es cero."""
    c = Calculo()
    activos = c.usar("PUC_ACTIVOS_FIJOS")
    gasto = c.usar("PUC_GASTO_DEPRECIACION")
    if not activos or not gasto:
        return []
    saldos = hojas(saldos_vigentes(periodo))
    if not saldos:
        return []
    base = _suma(saldos, activos, "saldo_final")
    dep = _suma(saldos, gasto, "debito")
    if base > 0 and dep <= 0:
        return [Resultado(clave=str(periodo), titulo="Activos fijos sin gasto de depreciación en el mes",
                          detalle=f"Activos fijos por {base:,.0f} y gasto de depreciación del mes en cero.",
                          cifras={"activos_fijos": base, "depreciacion_mes": dep})]
    return []


@regla("NOM001", "cierre", "Gasto de personal sin provisiones laborales", "media",
       "Código Sustantivo del Trabajo: cesantías, intereses, prima y vacaciones se causan mensualmente")
def provisiones_laborales(periodo):
    """Hay gasto de personal en el mes pero no se causaron las provisiones de prestaciones."""
    c = Calculo()
    personal = c.usar("PUC_GASTO_PERSONAL")
    provisiones = c.usar("PUC_PROVISIONES_LABORALES")
    if not personal or not provisiones:
        return []
    saldos = hojas(saldos_vigentes(periodo))
    if not saldos:
        return []
    gasto = _suma(saldos, personal, "debito")
    prov = _suma(saldos, provisiones, "credito")
    if gasto > 0 and prov <= 0:
        return [Resultado(clave=str(periodo), titulo="Hay gasto de personal pero no provisiones laborales",
                          detalle=f"Gasto de personal del mes {gasto:,.0f}; créditos a provisiones en cero.",
                          cifras={"gasto_personal": gasto, "provisiones": prov})]
    return []
