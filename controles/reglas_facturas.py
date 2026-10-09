import re
from collections import defaultdict
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


def indice_documentos(periodo):
    """documento normalizado -> movimientos (periodo anterior, actual y siguiente)."""
    indice = defaultdict(list)
    qs = Movimiento.objects.filter(
        periodo__in=_periodos_cercanos(periodo), archivo__vigente=True
    ).exclude(documento="").select_related("cuenta")
    for m in qs:
        indice[norm_doc(m.documento)].append(m)
    return indice


def hay_auxiliares(periodo):
    return ArchivoCargado.objects.filter(tipo="auxiliar", periodo=periodo, vigente=True).exists()


def movimientos_de(f, indice):
    llaves = {norm_doc(f.numero_completo), norm_doc(f.numero)}
    encontrados = []
    for k in llaves:
        encontrados += indice.get(k, [])
    # Si se conoce el NIT del tercero en el movimiento, debe coincidir
    nit = f.nit_tercero
    return [m for m in {id(x): x for x in encontrados}.values() if not m.nit or m.nit == nit]


def valor_causado(f, movs):
    """Valor causado en cartera (emitidas) o cuentas por pagar (recibidas) si hay parámetros de cuentas."""
    if f.sentido == "recibida":
        pref = Parametro.obtener_o("PUC_CUENTAS_POR_PAGAR")
        if not pref:
            return None
        return sum((m.credito - m.debito for m in movs if any(m.cuenta.codigo.startswith(p) for p in pref)), Decimal("0"))
    pref = Parametro.obtener_o("PUC_CARTERA")
    if not pref:
        return None
    return sum((m.debito - m.credito for m in movs if any(m.cuenta.codigo.startswith(p) for p in pref)), Decimal("0"))


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
        causado_firmado = causado if not f.es_nota_credito else -abs(causado)
        if abs(abs(causado_firmado) - abs(esperado_total)) > TOL and abs(abs(causado_firmado) - abs(esperado_neto)) > TOL:
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
