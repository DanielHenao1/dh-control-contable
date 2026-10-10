"""Borrador del formulario 350 (declaración de retención en la fuente) a partir del balance y los auxiliares del mes.

Es un borrador propio para contrastar con el que presenta el contratista; nunca se presenta desde aquí.
Reglas (ver docs/reglas/formulario_350.md):
- Retención practicada del mes = créditos del mes de las cuentas de retención (2365). Los débitos son el pago de la retención
  del mes anterior a la DIAN y no se restan.
- Cada subcuenta se asigna a un concepto del formulario con el parámetro RETEFUENTE_MAPA_CUENTAS (por prefijo de cuenta).
- La base se estima como retención ÷ tarifa; la tarifa sale del nombre de la subcuenta de World Office (por ejemplo «… 11%»).
- Personas jurídicas o naturales según el tercero de cada movimiento del auxiliar: maestro de terceros (por NIT o por nombre) y, si falta, el NIT o el nombre.
- Cada casilla se aproxima al múltiplo de mil más cercano (Estatuto Tributario art. 577) y los totales suman las casillas aproximadas.
"""
import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from contabilidad.models import Movimiento, saldos_vigentes
from empresa.models import Periodo
from terceros.servicios import ClasificadorDePersonas

from .comun import CERO, Calculo, hojas

# Concepto: (clave, etiqueta, (casilla base, casilla retención) jurídicas, ídem naturales). Numeración tomada del formulario 350
# de la declaración presentada de agosto de 2026; confirmar contra el formulario vigente cuando cambie.
CONCEPTOS_RENTA = [
    ("rentas_trabajo", "Rentas de trabajo", None, (77, 93)),
    ("rentas_pensiones", "Rentas de pensiones", None, (78, 94)),
    ("honorarios", "Honorarios", (29, 42), (79, 95)),
    ("comisiones", "Comisiones", (30, 43), (80, 96)),
    ("servicios", "Servicios", (31, 44), (81, 97)),
    ("rendimientos", "Rendimientos financieros e intereses", (32, 45), (82, 98)),
    ("arrendamientos", "Arrendamientos (muebles e inmuebles)", (33, 46), (83, 99)),
    ("regalias", "Regalías y explotación de la propiedad intelectual", (34, 47), (84, 100)),
    ("dividendos", "Dividendos y participaciones", (35, 48), (85, 101)),
    ("compras", "Compras", (36, 49), (86, 102)),
    ("tarjetas", "Transacciones con tarjetas débito y crédito", (37, 50), (87, 103)),
    ("construccion", "Contratos de construcción", (38, 51), (88, 104)),
    ("activos_fijos", "Enajenación de activos fijos de personas naturales", None, (89, 105)),
    ("loterias", "Loterías, rifas, apuestas y similares", (39, 52), (90, 106)),
    ("hidrocarburos", "Hidrocarburos, carbón y demás productos mineros", (40, 53), (91, 107)),
    ("otros_pagos", "Otros pagos sujetos a retención", (41, 54), (92, 108)),
]
AUTORRETENCIONES = [
    ("auto_ventas", "Autorretención · Ventas", (60, 69), (113, 121)),
    ("auto_honorarios", "Autorretención · Honorarios", (61, 70), (114, 122)),
    ("auto_comisiones", "Autorretención · Comisiones", (62, 71), (115, 123)),
    ("auto_servicios", "Autorretención · Servicios", (63, 72), (116, 124)),
    ("auto_rendimientos", "Autorretención · Rendimientos financieros", (64, 73), (117, 125)),
    ("auto_otros", "Autorretención · Otros conceptos", (67, 76), (120, 128)),
]
TODOS = CONCEPTOS_RENTA + AUTORRETENCIONES
CLAVES = {c[0] for c in TODOS}
CASILLA_RETEIVA = 131  # «A responsables del impuesto sobre las ventas»
TARIFA_EN_NOMBRE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def a_miles(valor):
    return (valor / Decimal(1000)).quantize(Decimal(1), rounding=ROUND_HALF_UP) * Decimal(1000)


def tarifa_del_nombre(nombre):
    m = TARIFA_EN_NOMBRE.search(nombre or "")
    return Decimal(m.group(1).replace(",", ".")) if m else None


def _mapa(c, fecha):
    """Prefijo de cuenta -> clave de concepto, según RETEFUENTE_MAPA_CUENTAS («236515=honorarios,23657501=auto_ventas»)."""
    mapa = {}
    for par in c.usar("RETEFUENTE_MAPA_CUENTAS", fecha, defecto=[]) or []:
        prefijo, _, clave = par.partition("=")
        if clave.strip() in CLAVES:
            mapa[prefijo.strip()] = clave.strip()
        else:
            c.advertencias.append(f"RETEFUENTE_MAPA_CUENTAS: «{par}» no corresponde a un concepto del formulario.")
    return mapa


def _clave_de(codigo, mapa):
    for prefijo in sorted(mapa, key=len, reverse=True):
        if codigo.startswith(prefijo):
            return mapa[prefijo]
    return None


def _reparto(periodo, codigo, clasificador, origenes):
    """Proporción de los créditos de una cuenta por tipo de persona ({'juridica': x, 'natural': y}, suman 1) o None."""
    por_tipo, sin_tercero = defaultdict(lambda: CERO), CERO
    for nit, nombre, credito in Movimiento.objects.filter(
        periodo=periodo, archivo__vigente=True, cuenta__codigo=codigo, credito__gt=0
    ).values_list("nit", "tercero_nombre", "credito"):
        tipo, origen = clasificador.clasificar(nit, nombre)
        if tipo:
            por_tipo[tipo] += credito
            origenes[origen] += 1
        else:
            sin_tercero += credito
    total = sum(por_tipo.values(), CERO)
    if not total:
        return None
    return {t: v / total for t, v in por_tipo.items()}


def borrador_350(periodo: Periodo):
    c = Calculo()
    prefijos = c.usar("PUC_RETEFUENTE", periodo.fin, defecto=[]) or []
    mapa = _mapa(c, periodo.fin)
    crudo = {clave: {"j": [CERO, CERO], "n": [CERO, CERO]} for clave, *_ in TODOS}  # [base, retención]
    cuentas = [s for s in hojas(saldos_vigentes(periodo).select_related("cuenta")) if any(s.cuenta.codigo.startswith(p) for p in prefijos)]
    if not cuentas:
        c.advertencias.append("No hay balance cargado con cuentas de retención en la fuente para el periodo.")
    clasificador, origenes = ClasificadorDePersonas(), defaultdict(int)
    hay_auxiliar = Movimiento.objects.filter(periodo=periodo, archivo__vigente=True).exists()
    if cuentas and not hay_auxiliar:
        c.advertencias.append("Sin libro auxiliar no se puede separar personas jurídicas y naturales: todo se muestra como personas jurídicas.")
    total_balance, debitos, sin_clasificar, sin_tarifa, sin_mapa = CERO, CERO, CERO, [], []
    for s in cuentas:
        debitos += s.debito
        valor = s.credito  # retención practicada en el mes
        if not valor:
            continue
        total_balance += valor
        clave = _clave_de(s.cuenta.codigo, mapa)
        if clave is None:
            clave = "otros_pagos"
            sin_mapa.append(s.cuenta.codigo)
        reparto = _reparto(periodo, s.cuenta.codigo, clasificador, origenes) if hay_auxiliar else None
        if reparto is None:
            reparto = {"juridica": Decimal(1)}
            if hay_auxiliar:
                sin_clasificar += valor
        tarifa = tarifa_del_nombre(s.cuenta.nombre)
        if not tarifa:
            sin_tarifa.append(s.cuenta.codigo)
        for tipo, parte in reparto.items():
            destino = crudo[clave]["j" if tipo == "juridica" else "n"]
            retencion = valor * parte
            destino[1] += retencion
            if tarifa:
                destino[0] += retencion * Decimal(100) / tarifa
    if sin_mapa:
        c.advertencias.append(f"Cuentas sin concepto en RETEFUENTE_MAPA_CUENTAS ({', '.join(sorted(set(sin_mapa)))}): se mostraron en «Otros pagos».")
    if sin_tarifa:
        c.advertencias.append(f"Sin tarifa en el nombre de la cuenta ({', '.join(sorted(set(sin_tarifa)))}): la base de esas retenciones queda en 0.")
    if sin_clasificar:
        c.advertencias.append("Hay retenciones cuyo tercero no está en el auxiliar: se mostraron como personas jurídicas.")
    if origenes["nit"] or origenes["nombre"]:
        c.advertencias.append(
            f"Tipo de persona deducido sin el maestro de terceros: {origenes['nit']} movimiento(s) por el NIT y {origenes['nombre']} por el nombre "
            "(un nombre con SAS, LTDA, SOCIEDAD, etc. es persona jurídica; el resto, natural). Cargue el maestro de terceros para confirmarlo."
        )
    filas, total_renta = [], CERO
    for clave, etiqueta, jur, nat in TODOS:
        fila = {"clave": clave, "etiqueta": etiqueta, "autorretencion": clave.startswith("auto_")}
        for lado, casillas, destino in (("j", jur, crudo[clave]["j"]), ("n", nat, crudo[clave]["n"])):
            if casillas is None:
                fila[lado] = None
                continue
            base, ret = a_miles(destino[0]), a_miles(destino[1])
            total_renta += ret
            fila[lado] = {"casilla_base": casillas[0], "base": base, "casilla_ret": casillas[1], "retencion": ret}
        filas.append(fila)
    from empresa.models import Parametro

    pref_iva = Parametro.obtener_o("PUC_RETEIVA", [], periodo.fin) or []
    reteiva = a_miles(sum((s.credito for s in hojas(saldos_vigentes(periodo).select_related("cuenta"))
                           if any(s.cuenta.codigo.startswith(p) for p in pref_iva)), CERO))
    total_retenciones = total_renta + reteiva
    c.valores.update({
        "total_retenciones_renta": total_renta, "retenciones_iva": reteiva, "total_retenciones": total_retenciones,
        "creditos_del_balance": total_balance, "debitos_del_balance": debitos,
    })
    c.supuestos += [
        "Retención practicada del mes = créditos del mes de las cuentas de retención; los débitos (pago a la DIAN del mes anterior) no se restan.",
        "La base de cada concepto se estima como retención ÷ tarifa de la subcuenta; si el contratista la calcula desde los documentos, puede diferir.",
        "Cada casilla se aproxima al múltiplo de mil más cercano (E.T. art. 577).",
        "Faltan por diligenciar a mano: retenciones en exceso o anuladas (casilla 129), timbre (135), sanciones (137) y el pago.",
    ]
    return {"filas": filas, "calculo": c.como_dict(), "valores": c.valores, "total_renta": total_renta, "reteiva": reteiva,
            "total_retenciones": total_retenciones, "casilla_reteiva": CASILLA_RETEIVA}
