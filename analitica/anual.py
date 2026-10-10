"""Consolidado anual: qué hay cargado mes a mes, resultados del año y la base de la información exógena.

Todo es aritmética sobre lo ya importado; no se presenta nada. Los umbrales de exógena son parámetros con vigencia.
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from contabilidad.models import Movimiento
from controles.reglas_exogena import meses_con_auxiliares
from empresa.models import ArchivoCargado, Parametro, ParametroPendiente
from facturacion.models import Factura

CERO = Decimal("0")
MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def cobertura(anio):
    """Por mes: ¿hay balance, auxiliares y facturas vigentes?"""
    balances = set(ArchivoCargado.objects.filter(tipo="balance", vigente=True, periodo__anio=anio).values_list("periodo__mes", flat=True))
    auxiliares = meses_con_auxiliares(anio)
    facturas = set(Factura.objects.filter(archivo__vigente=True, periodo__anio=anio).values_list("periodo__mes", flat=True))
    return [
        {"mes": m, "nombre": MESES[m], "balance": m in balances, "auxiliar": m in auxiliares, "facturas": m in facturas}
        for m in range(1, 13)
    ]


def _por_mes(anio, prefijo):
    qs = (Movimiento.objects.filter(archivo__vigente=True, periodo__anio=anio, cuenta__codigo__startswith=prefijo)
          .values("periodo__mes").annotate(d=Sum("debito"), c=Sum("credito")))
    return {r["periodo__mes"]: (r["d"] or CERO, r["c"] or CERO) for r in qs}


def resultados_por_mes(anio):
    """Ingresos, costos, gastos y utilidad de cada mes según los auxiliares (ingresos = créditos − débitos de la clase 4)."""
    ingresos, costos6, costos7, gastos = _por_mes(anio, "4"), _por_mes(anio, "6"), _por_mes(anio, "7"), _por_mes(anio, "5")
    filas = []
    total = defaultdict(lambda: CERO)
    for m in range(1, 13):
        i = ingresos.get(m, (CERO, CERO))
        ing = i[1] - i[0]
        cos = sum((x.get(m, (CERO, CERO))[0] - x.get(m, (CERO, CERO))[1] for x in (costos6, costos7)), CERO)
        g = gastos.get(m, (CERO, CERO))
        gas = g[0] - g[1]
        fila = {"mes": m, "nombre": MESES[m], "ingresos": ing, "costos": cos, "gastos": gas, "utilidad": ing - cos - gas}
        for k in ("ingresos", "costos", "gastos", "utilidad"):
            total[k] += fila[k]
        filas.append(fila)
    return filas, dict(total)


def pagos_por_tercero(anio):
    """Pagos del año (costos y gastos, clases 5, 6 y 7) por tercero: por NIT si el auxiliar lo trae, si no por nombre."""
    qs = (Movimiento.objects.filter(archivo__vigente=True, periodo__anio=anio)
          .filter(cuenta__codigo__regex=r"^[567]").values("nit", "tercero_nombre").annotate(d=Sum("debito"), c=Sum("credito")))
    por_clave, datos = defaultdict(lambda: CERO), {}
    for r in qs:
        clave = r["nit"] or (r["tercero_nombre"] or "").strip().upper() or "(sin tercero)"
        por_clave[clave] += (r["d"] or CERO) - (r["c"] or CERO)
        previo = datos.get(clave, ("", ""))
        datos[clave] = (r["nit"] or previo[0], r["tercero_nombre"] or previo[1])
    filas = [{"nit": datos[k][0], "nombre": datos[k][1] or ("" if k == "(sin tercero)" else k), "total": v}
             for k, v in sorted(por_clave.items(), key=lambda x: -x[1]) if v != 0]
    return filas


def _umbral(codigo, fecha):
    try:
        valor, aviso = Parametro.obtener_con_aviso(codigo, fecha)
    except ParametroPendiente:
        return None, "falta el parámetro"
    return valor, aviso


def obligacion_exogena(anio, ingresos, solo=None):
    completo = len(meses_con_auxiliares(anio)) >= 12
    """Dos comprobaciones por separado: la exógena nacional (DIAN) y la distrital de Bogotá tienen normas, umbrales y formatos distintos."""
    fecha = date(anio, 12, 31)
    try:
        uvt, aviso_uvt = Parametro.obtener_con_aviso("UVT", fecha)
    except ParametroPendiente:
        uvt, aviso_uvt = None, "falta el parámetro UVT"
    salida = []
    for codigo, nombre, norma, extra in (
        ("EXOGENA_DIAN_UMBRAL_UVT", "Exógena nacional (DIAN)",
         f"Resolución 000227 de 2025 de la DIAN y sus modificaciones (año gravable {anio})",
         "También están obligadas por su actividad (por ejemplo entidades financieras) sin importar el umbral."),
        ("EXOGENA_DISTRITAL_UMBRAL_UVT", "Exógena distrital (Bogotá)",
         "Resolución DDI-024115 de 2026 de la Secretaría Distrital de Hacienda (año gravable 2025)",
         "También están obligados los agentes de retención del distrito y otros sujetos por su actividad, sin importar el umbral."),
    ):
        if solo and codigo != solo:
            continue
        umbral, aviso = _umbral(codigo, fecha)
        fila = {"nombre": nombre, "norma": norma, "extra": extra, "umbral_uvt": umbral, "codigo": codigo, "aviso": aviso}
        if umbral in (None, "") or uvt is None:
            fila.update(estado="pendiente", texto="Falta el umbral en UVT o la UVT del año: cárgalos en Configuración → Parámetros.")
        else:
            tope = Decimal(str(umbral)) * Decimal(str(uvt))
            fila["tope"] = tope
            if ingresos >= tope:
                fila.update(estado="obligado", texto="Los ingresos del año alcanzan el umbral: debe reportar.")
            elif not completo:
                fila.update(estado="pendiente", texto="Con los meses cargados no se alcanza el umbral, pero faltan auxiliares de algunos meses: no es concluyente hasta cargar los 12.")
            else:
                fila.update(estado="no_obligado", texto="Los ingresos del año no alcanzan el umbral. Confirma que no lo obligue otra condición.")
        salida.append(fila)
    return salida, uvt, aviso_uvt
