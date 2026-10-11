"""Borrador del formulario 302 (declaración de ICA, avisos y tableros de Bogotá) a partir de los balances del bimestre.

Es un borrador propio para contrastar con el que presenta el contratista; nunca se presenta desde aquí. Reglas en
docs/reglas/formulario_302_ica.md. Resumen:
- Ingresos del bimestre = créditos − débitos de las cuentas de ingreso (clase 4) en los balances de los dos meses.
- Cada cuenta de ingreso va a una actividad según ICA_MAPA_INGRESOS (por defecto, la principal). Las devoluciones
  (ICA_CUENTAS_DEVOLUCIONES) se restan de la actividad de su cuenta y salen en el renglón 12.
- Lo que no sale de la contabilidad (ingresos fuera de Bogotá, exportaciones, activos fijos, deducciones, sanciones…) se
  registra en AjusteICA y se resta de la actividad principal.
- ICA = Σ base × tarifa por mil de cada actividad; avisos y tableros = ICA_AVISOS_PORCENTAJE del ICA.
- Retención de ICA que le practicaron = débitos − créditos del bimestre de ICA_CUENTAS_RETENCION_SUFRIDA.
- Cada renglón se aproxima al múltiplo de mil más cercano (E.T. art. 577) y los totales encadenan los renglones aproximados.
"""
import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from contabilidad.models import SaldoCuenta
from empresa.models import Periodo
from impuestos.models import AjusteICA

from .comun import CERO, Calculo, hojas
from .formulario_350 import a_miles
from .ica import tarifa_ica

BIMESTRES = {1: "enero-febrero", 2: "marzo-abril", 3: "mayo-junio", 4: "julio-agosto", 5: "septiembre-octubre", 6: "noviembre-diciembre"}


def _mapa(c, fecha):
    mapa = {}
    for par in c.usar("ICA_MAPA_INGRESOS", fecha, defecto=[]) or []:
        prefijo, _, destino = par.partition("=")
        if prefijo.strip() and destino.strip():
            mapa[prefijo.strip()] = destino.strip().lower() if destino.strip().lower() in ("principal", "ignorar") else destino.strip()
    return mapa


def _destino(codigo, mapa):
    for prefijo in sorted(mapa, key=len, reverse=True):
        if codigo.startswith(prefijo):
            return mapa[prefijo]
    return None


def _movimientos(periodos, prefijos):
    """{cuenta: (nombre, créditos, débitos)} de las cuentas hoja que empiezan por alguno de los prefijos, sumando los periodos."""
    total = defaultdict(lambda: ["", CERO, CERO])
    for p in periodos:
        qs = SaldoCuenta.objects.filter(periodo=p, archivo__vigente=True).select_related("cuenta")
        for s in hojas(qs):
            if any(s.cuenta.codigo.startswith(x) for x in prefijos):
                fila = total[s.cuenta.codigo]
                fila[0] = s.cuenta.nombre or fila[0]
                fila[1] += s.credito
                fila[2] += s.debito
    return total


def borrador_302(anio, bimestre):
    c = Calculo()
    m1, m2 = 2 * bimestre - 1, 2 * bimestre
    fecha = date(anio, m2, calendar.monthrange(anio, m2)[1])
    periodos = [p for p in (Periodo.objects.filter(anio=anio, mes=m).first() for m in (m1, m2)) if p is not None]
    con_balance = [p for p in periodos if SaldoCuenta.objects.filter(periodo=p, archivo__vigente=True).exists()]
    vacio = {"filas": [], "actividades": [], "calculo": c.como_dict(), "valores": {}, "bimestre": bimestre, "anio": anio, "etiqueta": BIMESTRES[bimestre]}
    if not con_balance:
        c.advertencias.append("No hay balance cargado de ninguno de los dos meses del bimestre.")
        vacio["calculo"] = c.como_dict()
        return vacio
    for mes in (m1, m2):
        if not any(p.mes == mes for p in con_balance):
            c.advertencias.append(f"Falta el balance de {mes:02d}/{anio}: el bimestre queda incompleto.")
    prefijos = c.usar("PUC_INGRESOS", fecha, defecto=["4"]) or ["4"]
    devoluciones = c.usar("ICA_CUENTAS_DEVOLUCIONES", fecha, defecto=[]) or []
    sufrida = c.usar("ICA_CUENTAS_RETENCION_SUFRIDA", fecha, defecto=[]) or []
    mapa = _mapa(c, fecha)
    pct = c.usar("ICA_AVISOS_PORCENTAJE", fecha, defecto=Decimal("15"))
    principal = c.usar("ICA_ACTIVIDAD_PRINCIPAL", fecha)
    bruto, devuelto, bases, sin_destino = CERO, CERO, defaultdict(lambda: CERO), []
    for codigo, (_nombre, cre, deb) in sorted(_movimientos(con_balance, prefijos).items()):
        destino = _destino(codigo, mapa)
        if destino is None:
            destino = "principal"
            sin_destino.append(codigo)
        if destino == "ignorar":
            continue
        actividad = principal if destino == "principal" else destino
        if any(codigo.startswith(d) for d in devoluciones):
            neto = deb - cre
            devuelto += neto
            bases[actividad] -= neto
        else:
            neto = cre - deb
            bruto += neto
            bases[actividad] += neto
    if sin_destino:
        c.advertencias.append(f"Cuentas de ingreso sin actividad en ICA_MAPA_INGRESOS ({', '.join(sin_destino[:6])}…): se asignaron a la actividad principal.")
    if len(bases) <= 1:
        c.advertencias.append("Todos los ingresos están en la actividad principal. Si la empresa tiene actividades secundarias, asigne sus subcuentas de ingreso en el parámetro ICA_MAPA_INGRESOS.")
    aj = AjusteICA.objects.filter(anio=anio, bimestre=bimestre).first() or AjusteICA(anio=anio, bimestre=bimestre)
    if aj.pk is None:
        c.advertencias.append("No hay datos manuales del bimestre (ingresos fuera de Bogotá, exportaciones, activos fijos, deducciones, sanciones): se tomaron en 0.")
    ba, bc = a_miles(bruto), a_miles(aj.ingresos_fuera_distrito)
    bt = ba - bc
    bb, ie, af, bd = a_miles(devuelto), a_miles(aj.exportaciones), a_miles(aj.activos_fijos), a_miles(aj.deducciones)
    be = bt - bb - ie - af - bd
    # Bases por actividad: las secundarias aproximadas; la principal queda con lo que falta para sumar el renglón 16.
    secundarias = {k: a_miles(v) for k, v in bases.items() if k != principal and v}
    base_principal = be - sum(secundarias.values(), CERO)
    actividades, impuesto_crudo = [], CERO
    for ciiu, base in [(principal, base_principal)] + sorted(secundarias.items()):
        t = tarifa_ica(ciiu, fecha) if ciiu else None
        tarifa = t.tarifa_por_mil if t is not None else None
        if tarifa is None:
            c.advertencias.append(f"Falta la tarifa de ICA de la actividad {ciiu}: cárguela en Conceptos de retención y tarifas ICA.")
        elif t.estado != "verificado":
            c.advertencias.append(f"La tarifa de ICA de {ciiu} ({tarifa} por mil) está por verificar con la tabla del Distrito.")
        impuesto = base * tarifa / Decimal(1000) if tarifa is not None else CERO
        impuesto_crudo += impuesto
        actividades.append({"ciiu": ciiu, "descripcion": getattr(t, "descripcion", ""), "base": base, "tarifa": tarifa, "impuesto": impuesto,
                            "principal": ciiu == principal})
    ic = a_miles(impuesto_crudo)
    bf = a_miles(ic * pct / Decimal(100))
    bg = a_miles(aj.unidades_adicionales)
    fu = ic + bf + bg
    retenido_crudo = sum((deb - cre for _n, cre, deb in _movimientos(con_balance, sufrida).values()), CERO)
    bi = a_miles(retenido_crudo)
    vs, dt, im = a_miles(aj.sanciones), a_miles(aj.descuento), a_miles(aj.intereses_mora)
    ha = fu - bi + vs - dt
    vp = ha if ha > 0 else CERO
    if ha < 0:
        c.advertencias.append("El saldo es a favor del contribuyente (renglón 24 negativo): no hay valor a pagar.")
    tp = vp + im
    R = lambda n, cod, txt, v, manual=False: {"renglon": n, "codigo": cod, "concepto": txt, "valor": v, "manual": manual}  # noqa: E731
    filas = [
        R(9, "BA", "Total ingresos ordinarios y extraordinarios del periodo", ba),
        R(10, "BC", "Total ingresos obtenidos fuera del Distrito Capital", bc, True),
        R(11, "BT", "Total ingresos brutos obtenidos en el Distrito Capital (9 − 10)", bt),
        R(12, "BB", "Menos ingresos por devoluciones, rebajas y descuentos", bb),
        R(13, "IE", "Menos ingresos por exportaciones", ie, True),
        R(14, "AF", "Menos ingresos por venta de activos fijos", af, True),
        R(15, "BD", "Menos deducciones, exenciones y actividades no sujetas", bd, True),
        R(16, "BE", "Total ingresos netos gravables (11 − 12 − 13 − 14 − 15)", be),
        R(17, "IC", "Impuesto de industria y comercio", ic),
        R(18, "BF", f"Impuesto de avisos y tableros ({pct}% del renglón 17)", bf),
        R(19, "BG", "Valor por unidades comerciales adicionales", bg, True),
        R(20, "FU", "Total impuesto a cargo (17 + 18 + 19)", fu),
        R(21, "BI", "Valor retenido a título de impuesto de industria y comercio", bi),
        R(22, "VS", "Sanciones", vs, True),
        R(23, "DT", "Descuento tributario (Acuerdo 780 de 2020)", dt, True),
        R(24, "HA", "Total saldo a cargo (20 − 21 + 22 − 23)", ha),
        R(25, "VP", "Valor a pagar", vp),
        R(26, "IM", "Intereses de mora", im, True),
        R(27, "TP", "Total a pagar (25 + 26)", tp),
    ]
    c.valores.update({"ingresos_brutos": bruto, "devoluciones": devuelto, "retencion_sufrida": retenido_crudo, "total_a_pagar": tp})
    c.supuestos += [
        "Ingresos del bimestre = créditos − débitos de las cuentas de ingreso en los balances de los dos meses.",
        "Lo que no sale de la contabilidad (renglones 10, 13, 14, 15, 19, 22, 23 y 26) viene de «Datos manuales del bimestre» y se resta de la actividad principal.",
        "Cada renglón se aproxima al múltiplo de mil más cercano (E.T. art. 577); la base de la actividad principal es lo que falta para sumar el renglón 16.",
        "La retención de ICA que le practicaron sale de las cuentas de ICA_CUENTAS_RETENCION_SUFRIDA; la ReteICA que la empresa practica a sus proveedores se declara aparte.",
    ]
    return {"filas": filas, "actividades": actividades, "calculo": c.como_dict(), "valores": c.valores, "bimestre": bimestre,
            "anio": anio, "etiqueta": BIMESTRES[bimestre], "ajuste": aj}
