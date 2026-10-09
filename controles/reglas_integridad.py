from decimal import Decimal

from contabilidad.models import movimientos_vigentes, saldos_vigentes
from empresa.models import ArchivoCargado, Parametro
from impuestos.reglas.comun import hojas

from .motor import Resultado, regla

TOLERANCIA = Decimal("1")  # un peso de diferencia por redondeo


@regla("INT001", "integridad", "Débitos distintos de créditos en el balance", "alta",
       "Principio de partida doble (Decreto 2649 de 1993 art. 4, hoy Decreto 2420 de 2015)")
def debitos_vs_creditos(periodo):
    """La suma de débitos del balance debe ser igual a la de créditos."""
    saldos = hojas(saldos_vigentes(periodo))
    if not saldos:
        return []
    d = sum((s.debito for s in saldos), Decimal("0"))
    c = sum((s.credito for s in saldos), Decimal("0"))
    if abs(d - c) > TOLERANCIA:
        return [Resultado(
            clave="balance", titulo="Los débitos no son iguales a los créditos",
            detalle=f"Débitos {d:,.0f} vs créditos {c:,.0f}; diferencia {d - c:,.0f}.",
            cifras={"debitos": d, "creditos": c, "diferencia": d - c},
        )]
    return []


@regla("INT002", "integridad", "Saldo calculado distinto del saldo reportado", "alta",
       "Saldo final = saldo inicial ± movimiento según la naturaleza de la cuenta")
def saldo_calculado(periodo):
    """Por cuenta: saldo inicial + movimiento debe dar el saldo final del balance."""
    salida = []
    for s in saldos_vigentes(periodo):
        dif = s.saldo_calculado - s.saldo_final
        if abs(dif) > TOLERANCIA:
            salida.append(Resultado(
                clave=s.cuenta.codigo, titulo=f"Cuenta {s.cuenta.codigo}: el saldo no cuadra",
                detalle=f"{s.cuenta.nombre}: calculado {s.saldo_calculado:,.0f}, reportado {s.saldo_final:,.0f}.",
                cifras={"calculado": s.saldo_calculado, "reportado": s.saldo_final, "diferencia": dif},
            ))
    return salida


@regla("INT003", "integridad", "Cuenta con saldo de naturaleza contraria", "media",
       "Un activo con saldo crédito o un pasivo con saldo débito suele indicar un error de registro")
def naturaleza_contraria(periodo):
    """Cuentas de último nivel con saldo contrario a su naturaleza."""
    salida = []
    # El IVA descontable vive en una cuenta de pasivo (2408) pero su saldo normal es débito: no es un error.
    exentas = tuple(Parametro.obtener_o("PUC_IVA_DESCONTABLE", []) or [])
    for s in hojas(saldos_vigentes(periodo)):
        if s.cuenta.clase not in "123456" or abs(s.saldo_final) <= TOLERANCIA:
            continue
        if exentas and s.cuenta.codigo.startswith(exentas):
            continue
        contrario = s.saldo_final < 0
        if contrario:
            salida.append(Resultado(
                clave=s.cuenta.codigo, titulo=f"Cuenta {s.cuenta.codigo} con saldo contrario a su naturaleza",
                detalle=f"{s.cuenta.nombre}: saldo {s.saldo_final:,.0f} (naturaleza {'débito' if s.cuenta.naturaleza == 'D' else 'crédito'}).",
                cifras={"saldo": s.saldo_final},
            ))
    return salida


@regla("INT004", "integridad", "Periodo sin carga", "media", "Cada mes necesita balance y auxiliares")
def periodo_sin_carga(periodo):
    """Avisa si el periodo no tiene balance o auxiliares vigentes."""
    salida = []
    for tipo, etiqueta in (("balance", "balance de prueba"), ("auxiliar", "auxiliares")):
        if not ArchivoCargado.objects.filter(tipo=tipo, periodo=periodo, vigente=True).exists():
            salida.append(Resultado(clave=tipo, titulo=f"Falta cargar el {etiqueta} de {periodo}",
                                    detalle="Sin este archivo los controles del periodo no se pueden completar."))
    return salida


@regla("INT005", "integridad", "Asiento descuadrado en los auxiliares", "alta",
       "Cada comprobante debe tener débitos iguales a créditos")
def asientos_descuadrados(periodo):
    """Suma por comprobante: débitos y créditos deben coincidir."""
    por_comp = {}
    for m in movimientos_vigentes(periodo):
        if not m.comprobante:
            continue
        d, c = por_comp.get(m.comprobante, (Decimal("0"), Decimal("0")))
        por_comp[m.comprobante] = (d + m.debito, c + m.credito)
    return [
        Resultado(clave=comp, titulo=f"Comprobante {comp} descuadrado",
                  detalle=f"Débitos {d:,.0f} vs créditos {c:,.0f}.", cifras={"debitos": d, "creditos": c})
        for comp, (d, c) in por_comp.items() if abs(d - c) > TOLERANCIA
    ]


@regla("INT006", "integridad", "Documento duplicado en los auxiliares", "media",
       "El mismo documento y tercero con el mismo valor puede ser un registro duplicado")
def movimientos_duplicados(periodo):
    """Mismo documento, tercero, cuenta y valor repetidos en distintos comprobantes."""
    vistos, salida = {}, []
    for m in movimientos_vigentes(periodo):
        if not m.documento:
            continue
        clave = (m.documento, m.nit, m.cuenta_id, m.debito, m.credito)
        if (m.debito or m.credito) and clave in vistos and vistos[clave] != m.comprobante:
            salida.append(Resultado(
                clave=f"{m.documento}|{m.nit}|{m.cuenta.codigo}|{m.debito}|{m.credito}",
                titulo=f"Documento {m.documento} aparece registrado más de una vez",
                detalle=f"Cuenta {m.cuenta.codigo}, valor {max(m.debito, m.credito):,.0f}; comprobantes {vistos[clave]} y {m.comprobante}.",
                cifras={"debito": m.debito, "credito": m.credito},
            ))
        vistos.setdefault(clave, m.comprobante)
    return salida
