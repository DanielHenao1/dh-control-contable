"""Utilidades compartidas por las reglas tributarias deterministas."""
from decimal import Decimal

from contabilidad.models import SaldoCuenta, saldos_vigentes
from empresa.models import Parametro, ParametroPendiente, Periodo

CERO = Decimal("0")


class Calculo:
    """Resultado de un cálculo: valores, supuestos y advertencias visibles al usuario."""

    def __init__(self):
        self.valores = {}
        self.supuestos = []
        self.advertencias = []

    def usar(self, codigo, fecha=None, defecto=None):
        """Lee un parámetro; si falta, lo anota como advertencia y devuelve el defecto."""
        try:
            valor, aviso = Parametro.obtener_con_aviso(codigo, fecha)
        except ParametroPendiente:
            self.advertencias.append(f"Falta el parámetro {codigo}: no se puede calcular esa parte.")
            return defecto
        if aviso:
            self.advertencias.append(f"{aviso}: confirmarlo con el contador.")
        return valor

    def como_dict(self):
        return {
            "valores": {k: str(v) if isinstance(v, Decimal) else v for k, v in self.valores.items()},
            "supuestos": self.supuestos,
            "advertencias": sorted(set(self.advertencias)),
        }


def tolerancia():
    return Parametro.obtener_o("TOLERANCIA_PESOS", Decimal("1"))


def hojas(saldos):
    """Cuentas de último nivel (ninguna otra cuenta del balance las usa como prefijo)."""
    saldos = list(saldos)
    codigos = sorted({s.cuenta.codigo for s in saldos})
    padres = set()
    for i, c in enumerate(codigos[:-1]):
        # al estar ordenados, si el siguiente empieza por c, c es padre
        if codigos[i + 1].startswith(c):
            padres.add(c)
    return [s for s in saldos if s.cuenta.codigo not in padres]


def saldo_positivo(s):
    """Saldo final expresado según la naturaleza de la cuenta (ingresos y pasivos en positivo)."""
    return s.saldo_final


def ultimo_balance(anio, hasta_mes=12):
    """Periodo más reciente con balance vigente en el año, hasta `hasta_mes`."""
    for p in Periodo.objects.filter(anio=anio, mes__lte=hasta_mes).order_by("-mes"):
        if saldos_vigentes(p).exists():
            return p
    return None


def total_clase(periodo, prefijos):
    """Suma de saldos finales (hojas) de las cuentas que empiezan por alguno de los prefijos."""
    total = CERO
    for s in hojas(saldos_vigentes(periodo)):
        if any(s.cuenta.codigo.startswith(p) for p in prefijos):
            total += s.saldo_final
    return total


def movimiento_neto(periodo, prefijos, naturaleza):
    """Movimiento del mes en cuentas por prefijo, positivo según la naturaleza (C: créd-déb)."""
    qs = SaldoCuenta.objects.filter(periodo=periodo, archivo__vigente=True)
    total = CERO
    for s in hojas(qs.select_related("cuenta")):
        if any(s.cuenta.codigo.startswith(p) for p in prefijos):
            total += (s.credito - s.debito) if naturaleza == "C" else (s.debito - s.credito)
    return total
