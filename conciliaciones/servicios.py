"""Conciliaciones: cada una devuelve filas {concepto, columnas..., diferencia} listas para mostrar."""
from collections import defaultdict
from decimal import Decimal
from itertools import combinations

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
    """Cartera (13) o proveedores (22): saldo del mes por tercero según auxiliares.

    Se agrupa por NIT; si el auxiliar no trae NIT (World Office solo exporta el nombre) se agrupa por nombre.
    """
    por_tercero = defaultdict(lambda: CERO)
    datos = {}
    for m in movimientos_vigentes(periodo):
        if any(m.cuenta.codigo.startswith(p) for p in prefijos):
            nombre = (m.tercero_nombre or "").strip()
            clave = m.nit or nombre or "(sin tercero)"
            por_tercero[clave] += signo * (m.debito - m.credito)
            datos[clave] = (m.nit, nombre)
    filas = [
        {"nit": datos.get(c, ("", ""))[0], "nombre": datos.get(c, ("", ""))[1] or ("" if c == "(sin tercero)" else c), "saldo": v}
        for c, v in sorted(por_tercero.items(), key=lambda x: -abs(x[1]))
    ]
    return {"filas": filas, "total": sum((f["saldo"] for f in filas), CERO),
            "sin_tercero": por_tercero.get("(sin tercero)", CERO)}


def cuentas_de_banco(periodo):
    """Cuentas de caja y bancos (11…) con movimientos en el periodo, para elegir cuál conciliar con el extracto."""
    cuentas = {}
    for m in movimientos_vigentes(periodo):
        if m.cuenta.codigo.startswith("11"):
            c = cuentas.setdefault(m.cuenta.codigo, {"codigo": m.cuenta.codigo, "nombre": m.cuenta.nombre, "movimientos": 0})
            c["movimientos"] += 1
    return sorted(cuentas.values(), key=lambda c: c["codigo"])


GASTOS_BANCO_DEFECTO = ["4X1000", "IVA", "SERVICIO", "CUOTA", "COBRO", "INTERESES", "RECHAZO", "COMISION"]
GASTOS_LIBROS_DEFECTO = ["GRAVAM", "COMISION", "GASTOS BANC", "CUOTA DE MANEJO"]


def _contiene(texto, patrones):
    texto = (texto or "").upper()
    return any(p.upper() in texto for p in patrones)


def conciliar_banco(periodo, prefijo_cuenta, dias=None, pesos=None):
    """Cruza el extracto bancario contra los auxiliares de la cuenta de banco, en cuatro pasos.

    Valor del extracto: + ingreso (débito en libros), - egreso (crédito en libros).
    1. Exactas: mismo valor (±`pesos`, por redondeos) y fecha ±`dias`, una sola vez.
    2. Misma cifra con fecha lejana: el valor coincide pero se registró en libros (o el banco lo movió) otro día del
       mes; queda marcada para revisar.
    3. Gastos bancarios agrupados: el banco cobra 4x1000, comisiones, IVA, cuotas e intereses partida por partida y en
       libros se causan en un solo asiento; si la suma de lo cobrado iguala ese asiento (±`pesos`) se concilian juntos.
    4. Agrupadas: una partida de un lado es la suma de 2 o 3 del otro (por ejemplo un pago al que en libros se le
       separó un descuento).
    Lo que no cruza queda como «solo en el extracto» o «solo en libros». Parámetros: CONCILIAR_BANCO_DIAS (3),
    CONCILIAR_BANCO_PESOS (1), CONCILIAR_BANCO_GASTOS y CONCILIAR_LIBROS_GASTOS (palabras que identifican los gastos).
    """
    dias = Parametro.obtener_o("CONCILIAR_BANCO_DIAS", 3) if dias is None else dias
    pesos = Decimal(str(Parametro.obtener_o("CONCILIAR_BANCO_PESOS", 1))) if pesos is None else Decimal(str(pesos))
    patrones_banco = Parametro.obtener_o("CONCILIAR_BANCO_GASTOS", GASTOS_BANCO_DEFECTO)
    patrones_libros = Parametro.obtener_o("CONCILIAR_LIBROS_GASTOS", GASTOS_LIBROS_DEFECTO)

    libros = [m for m in movimientos_vigentes(periodo) if m.cuenta.codigo.startswith(prefijo_cuenta)]
    banco = list(MovimientoBanco.objects.filter(periodo=periodo, archivo__vigente=True))
    valor_libro = {m.id: m.debito - m.credito for m in libros}
    libres_banco = list(banco)
    libres_libros = list(libros)
    exactas, con_revision = 0, []

    def cruzar(max_dias):
        """Empareja uno a uno por valor y fecha; devuelve los pares (banco, libro)."""
        pares = []
        for b in list(libres_banco):
            for m in libres_libros:
                if abs(valor_libro[m.id] - b.valor) <= pesos and (max_dias is None or abs((m.fecha - b.fecha).days) <= max_dias):
                    pares.append((b, m))
                    libres_banco.remove(b)
                    libres_libros.remove(m)
                    break
        return pares

    exactas = len(cruzar(dias))
    for b, m in cruzar(None):
        con_revision.append({"motivo": f"Mismo valor, pero con {abs((m.fecha - b.fecha).days)} días de diferencia entre el banco y los libros",
                             "banco": [b], "libros": [m]})

    gastos = [b for b in libres_banco if _contiene(b.descripcion, patrones_banco)]
    if gastos:
        total = sum((b.valor for b in gastos), CERO)
        for m in list(libres_libros):
            if _contiene(m.descripcion, patrones_libros) and abs(valor_libro[m.id] - total) <= pesos:
                con_revision.append({"motivo": f"Gastos bancarios: {len(gastos)} cobros del banco (4x1000, comisiones, IVA…) causados en un solo asiento",
                                     "banco": gastos, "libros": [m]})
                for b in gastos:
                    libres_banco.remove(b)
                libres_libros.remove(m)
                break

    def agrupar(un_lado, otro_lado, valor_un, valor_otro, etiqueta_un):
        for x in list(un_lado):
            candidatos = [y for y in otro_lado if (valor_otro(y) > 0) == (valor_un(x) > 0)][:40]
            for n in (2, 3):
                hallado = next((c for c in combinations(candidatos, n)
                                if abs(sum(valor_otro(y) for y in c) - valor_un(x)) <= pesos), None)
                if hallado:
                    yield x, list(hallado), etiqueta_un
                    un_lado.remove(x)
                    for y in hallado:
                        otro_lado.remove(y)
                    break

    for b, ms, _ in agrupar(libres_banco, libres_libros, lambda b: b.valor, lambda m: valor_libro[m.id], "banco"):
        con_revision.append({"motivo": f"Una partida del banco es la suma de {len(ms)} partidas de libros", "banco": [b], "libros": ms})
    for m, bs, _ in agrupar(libres_libros, libres_banco, lambda m: valor_libro[m.id], lambda b: b.valor, "libros"):
        con_revision.append({"motivo": f"Una partida de libros es la suma de {len(bs)} partidas del banco", "banco": bs, "libros": [m]})

    return {
        "conciliadas": exactas + len(con_revision), "exactas": exactas, "con_revision": con_revision,
        "solo_banco": libres_banco, "solo_libros": libres_libros,
        "total_banco": sum((b.valor for b in banco), CERO),
        "total_libros": sum(valor_libro.values(), CERO),
        "tolerancia_dias": dias, "tolerancia_pesos": pesos,
    }
