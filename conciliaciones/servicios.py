"""Conciliaciones: cada una devuelve filas {concepto, columnas..., diferencia} listas para mostrar."""
from collections import defaultdict

from contabilidad.models import SaldoCuenta, movimientos_vigentes
from empresa.models import Parametro
from facturacion.models import facturas_vigentes
from impuestos.reglas.comun import CERO, hojas
from impuestos.reglas.iva import borrador_iva, declarado_iva, iva_contabilidad
from impuestos.reglas.retencion import borrador_retefuente, declarado_retefuente, reteiva_contable

from .models import MovimientoBanco


def _dif(a, b):
    return None if a is None or b is None else a - b


def conciliar_iva(anio, indice):
    """IVA del período (cuatrimestre o bimestre): propio (FE) vs contabilidad vs declarado."""
    c = borrador_iva(anio, indice)
    mes_ini, mes_fin = [int(x) for x in c.valores["meses"].split("-")]
    gen_c, des_c = iva_contabilidad(anio, mes_ini, mes_fin, c)
    declarado = declarado_iva(anio, indice)
    saldo_c = None if gen_c is None else gen_c - des_c
    filas = [
        {"concepto": "IVA generado", "propio": c.valores["iva_generado"], "contabilidad": gen_c},
        {"concepto": "IVA descontable", "propio": c.valores["iva_descontable"], "contabilidad": des_c},
        {"concepto": "Saldo a pagar (a favor si es negativo)", "propio": c.valores["saldo"],
         "contabilidad": saldo_c, "declarado": declarado},
    ]
    for f in filas:
        f["dif_contabilidad"] = _dif(f["propio"], f["contabilidad"])
        f["dif_declarado"] = _dif(f["propio"], f.get("declarado"))
    return {"filas": filas, "calculo": c.como_dict(), "meses": (mes_ini, mes_fin)}


def conciliar_retencion(periodo):
    c = borrador_retefuente(periodo)
    v = c.valores
    declarado = declarado_retefuente(periodo)
    filas = [{
        "concepto": "Retención en la fuente",
        "teorico": v.get("teorico"), "registrado": v.get("retenido_registrado"),
        "contabilidad": v.get("contabilidad"), "declarado": declarado,
        "dif_teorico": _dif(v.get("retenido_registrado"), v.get("teorico")),
        "dif_contabilidad": _dif(v.get("retenido_registrado"), v.get("contabilidad")),
        "dif_declarado": _dif(v.get("contabilidad") if v.get("contabilidad") is not None else v.get("retenido_registrado"), declarado),
    }]
    filas.append({"concepto": "Retención de IVA (ReteIVA), solo contabilidad", "contabilidad": reteiva_contable(periodo)})
    return {"filas": filas, "calculo": c.como_dict()}


def conciliar_facturas(periodo):
    """Resumen DIAN vs contabilidad del mes usando los hallazgos de facturas ya calculados."""
    from controles.reglas_facturas import hay_auxiliares, indice_documentos, movimientos_de

    emitidas = list(facturas_vigentes(periodo, "emitida"))
    recibidas = list(facturas_vigentes(periodo, "recibida"))
    auxiliares = hay_auxiliares(periodo)
    indice = indice_documentos(periodo) if auxiliares else {}
    filas = []
    for etiqueta, lista in (("Ventas (emitidas)", emitidas), ("Compras (recibidas)", recibidas)):
        causadas = sin_causar = 0
        valor_total = valor_sin = CERO
        for f in lista:
            valor_total += f.signo * f.total
            if auxiliares and not movimientos_de(f, indice):
                sin_causar += 1
                valor_sin += f.signo * f.total
            else:
                causadas += 1
        filas.append({"concepto": etiqueta, "facturas": len(lista), "total": valor_total,
                      "causadas": causadas if auxiliares else None, "sin_causar": sin_causar if auxiliares else None,
                      "valor_sin_causar": valor_sin if auxiliares else None})
    return {"filas": filas, "auxiliares_cargados": auxiliares}


def conciliar_auxiliares_vs_balance(periodo, grupos=None):
    """Por grupo de cuentas, el movimiento de los auxiliares debe igualar el del balance."""
    grupos = grupos or Parametro.obtener_o("CONCILIAR_GRUPOS", ["13", "22", "23", "24", "11"])
    saldos = hojas(SaldoCuenta.objects.filter(periodo=periodo, archivo__vigente=True).select_related("cuenta"))
    movs = list(movimientos_vigentes(periodo))
    filas = []
    for g in grupos:
        bal = sum((s.debito - s.credito for s in saldos if s.cuenta.codigo.startswith(g)), CERO)
        aux = sum((m.debito - m.credito for m in movs if m.cuenta.codigo.startswith(g)), CERO)
        filas.append({"concepto": f"Grupo {g}", "balance": bal, "auxiliares": aux, "diferencia": bal - aux})
    return {"filas": filas}


def conciliar_terceros(periodo, prefijos, signo=1):
    """Cartera (13) o proveedores (22): saldo del mes por tercero según auxiliares."""
    por_nit = defaultdict(lambda: CERO)
    nombres = {}
    for m in movimientos_vigentes(periodo):
        if any(m.cuenta.codigo.startswith(p) for p in prefijos):
            por_nit[m.nit or "(sin tercero)"] += signo * (m.debito - m.credito)
            nombres[m.nit] = m.tercero_nombre
    filas = [{"nit": n, "nombre": nombres.get(n, ""), "saldo": v} for n, v in sorted(por_nit.items(), key=lambda x: -abs(x[1]))]
    return {"filas": filas, "total": sum((f["saldo"] for f in filas), CERO),
            "sin_tercero": por_nit.get("(sin tercero)", CERO)}


def conciliar_banco(periodo, prefijo_cuenta, dias=3):
    """Cruza el extracto bancario contra los auxiliares de la cuenta de banco.

    Una partida concilia si coinciden valor y fecha (± `dias`), una sola vez.
    Valor del extracto: + ingreso (débito en libros), - egreso (crédito en libros).
    """
    libros = [m for m in movimientos_vigentes(periodo) if m.cuenta.codigo.startswith(prefijo_cuenta)]
    banco = list(MovimientoBanco.objects.filter(periodo=periodo, archivo__vigente=True))
    usados = set()
    solo_banco = []
    for b in banco:
        match = None
        for m in libros:
            if m.id in usados:
                continue
            if m.debito - m.credito == b.valor and abs((m.fecha - b.fecha).days) <= dias:
                match = m
                break
        if match:
            usados.add(match.id)
        else:
            solo_banco.append(b)
    solo_libros = [m for m in libros if m.id not in usados]
    return {
        "conciliadas": len(usados), "solo_banco": solo_banco, "solo_libros": solo_libros,
        "total_banco": sum((b.valor for b in banco), CERO),
        "total_libros": sum((m.debito - m.credito for m in libros), CERO),
        "tolerancia_dias": dias,
    }
