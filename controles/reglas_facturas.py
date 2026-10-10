import re
import unicodedata
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from contabilidad.models import Movimiento
from empresa.models import ArchivoCargado, Parametro, Periodo
from facturacion.models import facturas_vigentes

from .motor import Resultado, regla

TOL = Decimal("1")


def norm_doc(texto):
    t = re.sub(r"[\s\-_/\.]", "", str(texto or "")).upper()
    return t.lstrip("0") or t


def _periodos_cercanos(periodo):
    anio, mes = periodo.anio, periodo.mes
    ant = (anio - 1, 12) if mes == 1 else (anio, mes - 1)
    sig = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return Periodo.objects.filter(
        id__in=[p.id for p in Periodo.objects.all() if (p.anio, p.mes) in (ant, (anio, mes), sig)]
    )


class IndiceDocumentos(defaultdict):
    """documento normalizado -> movimientos, más la lista completa de movimientos (periodo anterior, actual y siguiente)."""

    def __init__(self):
        super().__init__(list)
        self.movs = []
        self.usados = set()  # movimientos ya asignados a una factura por la búsqueda por tercero y valor
        self.asignadas = {}  # id de factura -> movimientos encontrados (misma respuesta si se vuelve a preguntar)
        self.textos = []  # (movimiento, documento+descripción normalizados) para buscar el número de la factura


_SUFIJOS_SOCIETARIOS = {"SAS", "SA", "LTDA", "ESP", "SCA", "ZOMAC", "EU", "CIA", "LIMITADA"}


def norm_nombre(texto):
    """Nombre de tercero comparable: sin tildes ni puntuación, sin sufijos societarios y sin espacios."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().upper()
    t = re.sub(r"[^A-Z0-9]+", " ", t).strip()
    t = re.sub(r"\bS A S\b", "SAS", t)  # «S.A.S.», «S A S» y «SAS» son el mismo sufijo
    t = re.sub(r"\bS A\b", "SA", t)
    t = re.sub(r"\bE U\b", "EU", t)
    return "".join(w for w in t.split() if w not in _SUFIJOS_SOCIETARIOS)


_PALABRAS_VACIAS = {"DE", "DEL", "LA", "EL", "LOS", "LAS", "Y", "E", "CON", "PARA", "POR"}


def _palabras(texto):
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().upper()
    return {w for w in re.sub(r"[^A-Z0-9]+", " ", t).split() if len(w) > 1 and w not in _SUFIJOS_SOCIETARIOS and w not in _PALABRAS_VACIAS}


def mismo_tercero(a, b):
    """El mismo tercero aunque el nombre cambie un poco entre la DIAN y la contabilidad (siglas, razón social larga)."""
    na, nb = norm_nombre(a), norm_nombre(b)
    if not na or not nb:
        return False
    corto, largo = sorted((na, nb), key=len)
    if na == nb or (len(corto) >= 8 and corto in largo):
        return True
    pa, pb = _palabras(a), _palabras(b)
    menor, mayor = sorted((pa, pb), key=len)
    return len(menor) >= 2 and menor <= mayor


def indice_documentos(periodo):
    """documento normalizado -> movimientos (periodo anterior, actual y siguiente)."""
    indice = IndiceDocumentos()
    qs = Movimiento.objects.filter(
        periodo__in=_periodos_cercanos(periodo), archivo__vigente=True
    ).select_related("cuenta")
    for m in qs:
        indice.movs.append(m)
        indice.textos.append((m, norm_doc(f"{m.documento} {m.descripcion}")))
        if m.documento:
            indice[norm_doc(m.documento)].append(m)
    # Primero las facturas cuyo número aparece en la contabilidad: ese vínculo manda sobre la búsqueda por valor.
    for f in facturas_vigentes(periodo):
        directos = _directo(f, indice)
        if directos:
            indice.asignadas[f.id] = directos
            indice.usados.update(m.id for m in directos)
    return indice


def hay_auxiliares(periodo):
    return ArchivoCargado.objects.filter(tipo="auxiliar", periodo=periodo, vigente=True).exists()


VENTANA_DIAS = 45  # la causación puede registrarse varios días después de la fecha de emisión


def _cuentas_de_la_factura(f):
    """Prefijos de cuenta donde queda causada: pasivos (22 proveedores, 23 costos y gastos por pagar) o caja y bancos
    (11) si se pagó de contado, para las recibidas; cartera (13) para las emitidas."""
    if f.sentido == "recibida":
        base = Parametro.obtener_o("CAUSACION_CUENTAS_COMPRAS", ["22", "23", "11"])
        return list(base) + list(Parametro.obtener_o("PUC_CUENTAS_POR_PAGAR") or [])
    return list(Parametro.obtener_o("CAUSACION_CUENTAS_VENTAS", ["13"])) + list(Parametro.obtener_o("PUC_CARTERA") or [])


def movimientos_de(f, indice):
    """Movimientos contables que corresponden a la factura, buscados en tres pasos:

    1. el documento del movimiento es el número de la factura;
    2. el documento o la descripción del movimiento contienen el número completo de la factura (World Office
       registra «(DTS) FV FE 11407», con su propio consecutivo y prefijo);
    3. si el auxiliar guarda su propio consecutivo (compras: «(DTS) FC 1447»), mismo tercero y mismo valor en la cuenta
       por pagar o de cartera, dentro de una ventana de fechas.
    """
    if f.id in getattr(indice, "asignadas", {}):
        return indice.asignadas[f.id]
    resultado = _buscar_movimientos(f, indice)
    if hasattr(indice, "asignadas") and f.id is not None:
        indice.asignadas[f.id] = resultado
    return resultado


def _directo(f, indice):
    """Movimientos cuyo documento o descripción contienen el número de la factura."""
    llaves = {norm_doc(f.numero_completo), norm_doc(f.numero)}
    encontrados = []
    for k in llaves:
        encontrados += indice.get(k, [])
    completo = norm_doc(f.numero_completo)
    if not encontrados and len(completo) >= 5 and hasattr(indice, "textos"):
        encontrados = [m for m, texto in indice.textos if completo in texto]
    nit = f.nit_tercero
    return [m for m in {id(x): x for x in encontrados}.values() if not m.nit or m.nit == nit]


def _buscar_movimientos(f, indice):
    resultado = _directo(f, indice)
    if resultado or not hasattr(indice, "movs"):
        return resultado
    nit = f.nit_tercero
    prefijos = _cuentas_de_la_factura(f)
    esperado = {abs(f.total), abs(f.total - f.retenciones)}
    tolerancia = Decimal(str(Parametro.obtener_o("CAUSACION_TOLERANCIA_PESOS", 5)))
    nombre = f.nombre_emisor if f.sentido == "recibida" else f.nombre_receptor
    grupos = defaultdict(list)  # un mismo documento contable puede repartir la factura (cuenta por pagar + retención)
    for m in indice.movs:
        if not any(m.cuenta.codigo.startswith(p) for p in prefijos):
            continue
        if not (f.fecha - timedelta(days=5) <= m.fecha <= f.fecha + timedelta(days=VENTANA_DIAS)):
            continue
        if not ((m.nit and m.nit == nit) or mismo_tercero(m.tercero_nombre, nombre)):
            continue
        grupos[norm_doc(m.documento) or f"mov{m.id}"].append(m)
    for movs in grupos.values():
        if any(m.id in indice.usados for m in movs):
            continue  # ese asiento ya corresponde a otra factura

        def valor(m):
            if f.sentido == "recibida":
                return m.credito - m.debito if not f.es_nota_credito else m.debito - m.credito
            return m.debito - m.credito if not f.es_nota_credito else m.credito - m.debito

        solos = [m for m in movs if any(abs(valor(m) - e) <= tolerancia for e in esperado)]
        if solos:
            indice.usados.update(m.id for m in movs)
            return solos[:1]
        if any(abs(sum(valor(m) for m in movs if valor(m) > 0) - e) <= tolerancia for e in esperado):
            indice.usados.update(m.id for m in movs)
            return movs
    return resultado


def valor_causado(f, movs):
    """Valor con que quedó causada la factura (cuentas por pagar y retenciones en compras; cartera en ventas).

    Un mismo documento contable puede repartir la factura en varias cuentas, así que se suma por documento y se toma el
    documento cuyo valor más se acerca al de la factura. None si ninguno de los movimientos está en esas cuentas
    (por ejemplo, solo hay el pago en caja o bancos): no hay valor causado que comparar.
    """
    if f.sentido == "recibida":
        prefijos = ["22", "23"] + list(Parametro.obtener_o("PUC_CUENTAS_POR_PAGAR") or [])
    else:
        prefijos = ["13"] + list(Parametro.obtener_o("PUC_CARTERA") or [])
    excluir = Parametro.obtener_o("CAUSACION_CUENTAS_EXCLUIDAS", ["1355"])  # anticipo de impuestos y retenciones, no es cartera
    por_documento = defaultdict(lambda: Decimal("0"))
    for m in movs:
        if any(m.cuenta.codigo.startswith(p) for p in prefijos) and not any(m.cuenta.codigo.startswith(x) for x in excluir):
            neto = (m.credito - m.debito) if f.sentido == "recibida" else (m.debito - m.credito)
            por_documento[norm_doc(m.documento) or f"mov{m.id}"] += neto
    # la causación aumenta la cuenta; el pago o el recibo de caja la disminuye (y al revés en las notas crédito)
    valores = [abs(v) for v in por_documento.values() if (v < 0 if f.es_nota_credito else v > 0)]
    if not valores:
        return None
    objetivo = abs(f.total)
    return min(valores, key=lambda v: abs(v - objetivo))


@regla("FAC001", "facturas", "Factura DIAN sin causar", "alta",
       "Las facturas electrónicas recibidas deben estar registradas en la contabilidad (Estatuto Tributario art. 771-2)")
def sin_causar(periodo):
    """Factura DIAN sin documento equivalente en los auxiliares."""
    if not hay_auxiliares(periodo):
        return []
    indice = indice_documentos(periodo)
    salida = []
    for f in facturas_vigentes(periodo):
        if f.tipo_documento == "doc_soporte" and f.sentido == "emitida":
            continue
        if not movimientos_de(f, indice):
            lado = "venta" if f.sentido == "emitida" else "compra"
            salida.append(Resultado(
                clave=f"{f.sentido}|{f.nit_emisor}|{f.numero_completo}",
                titulo=f"Factura de {lado} {f.numero_completo} sin causar",
                detalle=f"{f.nombre_emisor or f.nit_emisor} · {f.fecha:%d-%m-%Y} · total {f.total:,.0f}.",
                cifras={"total": f.total, "iva": f.iva},
                evidencia={"factura_id": f.id},
            ))
    return salida


@regla("FAC002", "facturas", "Factura causada con valor distinto", "media",
       "La causación debe reflejar el valor de la factura electrónica")
def valor_distinto(periodo):
    """Compara el valor causado en cartera/cuentas por pagar con el total de la factura."""
    if not hay_auxiliares(periodo):
        return []
    indice = indice_documentos(periodo)
    salida = []
    for f in facturas_vigentes(periodo):
        movs = movimientos_de(f, indice)
        if not movs:
            continue
        causado = valor_causado(f, movs)
        if causado is None:
            continue
        esperado_total = f.signo * f.total
        esperado_neto = esperado_total - f.signo * f.retenciones
        tolerancia = Decimal(str(Parametro.obtener_o("CAUSACION_TOLERANCIA_PESOS", 5)))
        if abs(causado - abs(esperado_total)) > tolerancia and abs(causado - abs(esperado_neto)) > tolerancia:
            salida.append(Resultado(
                clave=f"{f.sentido}|{f.nit_emisor}|{f.numero_completo}",
                titulo=f"Factura {f.numero_completo} causada por un valor distinto",
                detalle=f"Factura {f.total:,.0f}; causado {abs(causado):,.0f}; diferencia {abs(f.total) - abs(causado):,.0f}.",
                cifras={"factura": f.total, "causado": abs(causado)},
                evidencia={"factura_id": f.id},
            ))
    return salida


@regla("FAC003", "facturas", "Factura duplicada", "alta", "Un mismo documento o CUFE no debe aparecer dos veces")
def duplicadas(periodo):
    """Mismo emisor y número, o mismo CUFE, repetidos."""
    vistos_num, vistos_cufe, salida = {}, {}, []
    for f in facturas_vigentes(periodo):
        k = (f.sentido, f.tipo_documento, f.nit_emisor, f.numero_completo)
        dup = k in vistos_num or (f.cufe and f.cufe in vistos_cufe)
        vistos_num.setdefault(k, f.id)
        if f.cufe:
            vistos_cufe.setdefault(f.cufe, f.id)
        if dup:
            salida.append(Resultado(
                clave=f"{f.sentido}|{f.nit_emisor}|{f.numero_completo}",
                titulo=f"Factura {f.numero_completo} duplicada",
                detalle=f"Aparece más de una vez en los archivos del periodo ({f.nombre_emisor or f.nit_emisor}).",
                cifras={"total": f.total},
            ))
    return salida


@regla("FAC004", "facturas", "Nota crédito sin vínculo a una factura", "media",
       "Las notas crédito deben referenciar la factura que corrigen")
def nota_sin_vinculo(periodo):
    """Nota crédito o débito sin documento afectado, o cuyo documento afectado no existe."""
    todas = {norm_doc(f.numero_completo) for f in facturas_vigentes() if f.tipo_documento == "factura"}
    salida = []
    for f in facturas_vigentes(periodo).filter(tipo_documento__in=["nota_credito", "nota_debito"]):
        if not f.documento_afectado:
            motivo = "no informa la factura que corrige"
        elif norm_doc(f.documento_afectado) not in todas:
            motivo = f"la factura {f.documento_afectado} no está en los archivos cargados"
        else:
            continue
        salida.append(Resultado(
            clave=f"{f.sentido}|{f.nit_emisor}|{f.numero_completo}",
            titulo=f"Nota {f.numero_completo} sin vínculo verificable",
            detalle=f"La nota {motivo}.", cifras={"total": f.total},
        ))
    return salida


@regla("FAC005", "facturas", "Fecha de factura fuera del periodo", "baja", "El periodo fiscal depende de la fecha de emisión")
def fuera_de_periodo(periodo):
    """Factura con fecha que no cae en el mes cargado."""
    return [
        Resultado(
            clave=f"{f.sentido}|{f.nit_emisor}|{f.numero_completo}",
            titulo=f"Factura {f.numero_completo} con fecha fuera de {periodo}",
            detalle=f"Fecha de emisión {f.fecha:%d-%m-%Y}.", cifras={"total": f.total},
        )
        for f in facturas_vigentes(periodo) if not (periodo.inicio <= f.fecha <= periodo.fin)
    ]


@regla("FAC006", "facturas", "Salto en la numeración de facturación", "media",
       "Control de numeración del facturador electrónico (autorización de numeración DIAN)")
def saltos_numeracion(periodo):
    """Números faltantes dentro de la secuencia de documentos emitidos por la empresa."""
    grupos = defaultdict(list)
    for f in facturas_vigentes(periodo, "emitida"):
        if f.numero.isdigit():
            grupos[(f.tipo_documento, f.prefijo)].append(int(f.numero))
    salida = []
    for (tipo, prefijo), numeros in grupos.items():
        n = sorted(set(numeros))
        faltan = [x for x in range(n[0], n[-1] + 1) if x not in set(n)]
        if faltan:
            muestra = ", ".join(str(x) for x in faltan[:15]) + ("…" if len(faltan) > 15 else "")
            salida.append(Resultado(
                clave=f"{tipo}|{prefijo}", titulo=f"Saltos en la numeración {prefijo or '(sin prefijo)'} ({tipo})",
                detalle=f"Faltan {len(faltan)} número(s) entre {n[0]} y {n[-1]}: {muestra}", cifras={"faltantes": len(faltan)},
            ))
    return salida
