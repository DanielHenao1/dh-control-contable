from datetime import date
from decimal import Decimal

from empresa.models import Parametro, ParametroPendiente
from impuestos.reglas.comun import Calculo
from impuestos.reglas.iva import (
    borrador_iva,
    declarado_iva,
    ingresos_brutos_anio,
    iva_contabilidad,
    iva_facturas,
    periodicidad_vigente,
    tramo_de,
)

from .motor import Resultado, regla

TOL = Decimal("1")


@regla("IVA001", "iva", "IVA de facturas electrónicas distinto del IVA contabilizado", "alta",
       "Estatuto Tributario art. 771-2 y 488: el IVA descontable y el generado se soportan en factura")
def fe_vs_contabilidad(periodo):
    """Compara el IVA de las facturas DIAN del mes con el movimiento de las cuentas de IVA."""
    gen_fe, des_fe, _, _ = iva_facturas(periodo.anio, periodo.mes, periodo.mes)
    gen_c, des_c = iva_contabilidad(periodo.anio, periodo.mes, periodo.mes)
    if gen_c is None:
        return []
    salida = []
    if abs(gen_fe - gen_c) > TOL:
        salida.append(Resultado(
            clave="generado", titulo="IVA generado: facturas DIAN vs contabilidad",
            detalle=f"Facturas {gen_fe:,.0f}; contabilidad {gen_c:,.0f}; diferencia {gen_fe - gen_c:,.0f}.",
            cifras={"facturas": gen_fe, "contabilidad": gen_c, "diferencia": gen_fe - gen_c}))
    if abs(des_fe - des_c) > TOL:
        salida.append(Resultado(
            clave="descontable", titulo="IVA descontable: facturas DIAN vs contabilidad",
            detalle=f"Facturas {des_fe:,.0f}; contabilidad {des_c:,.0f}; diferencia {des_fe - des_c:,.0f}.",
            cifras={"facturas": des_fe, "contabilidad": des_c, "diferencia": des_fe - des_c}))
    return salida


@regla("IVA002", "iva", "IVA propio distinto del declarado", "alta", "Conciliación del borrador propio con la declaración del contratista")
def propio_vs_declarado(periodo):
    """Al cierre del cuatrimestre, el saldo propio debe coincidir con lo declarado."""
    indice, _, mes_fin = tramo_de(periodo.anio, periodo.mes)
    if periodo.mes != mes_fin:
        return None
    declarado = declarado_iva(periodo.anio, indice)
    if declarado is None:
        return []
    propio = borrador_iva(periodo.anio, indice).valores["saldo"]
    if abs(propio - declarado) > TOL:
        return [Resultado(
            clave=f"{periodo.anio}-P{indice}", titulo=f"IVA {periodo.anio} período {indice}: propio vs declarado",
            detalle=f"Propio {propio:,.0f}; declarado {declarado:,.0f}; diferencia {propio - declarado:,.0f}.",
            cifras={"propio": propio, "declarado": declarado, "diferencia": propio - declarado})]
    return []


@regla("IVA003", "iva", "Periodicidad del IVA inconsistente con los ingresos", "alta",
       "Estatuto Tributario art. 600: bimestral si los ingresos brutos del año anterior son >= 92.000 UVT")
def periodicidad(periodo):
    """Alerta cuando los ingresos del año se acercan o superan el tope de periodicidad bimestral."""
    try:
        tope_uvt = Parametro.obtener("IVA_TOPE_BIMESTRAL_UVT", date(periodo.anio, 6, 1))
        uvt = Parametro.obtener("UVT", date(periodo.anio - 1, 12, 31))
    except ParametroPendiente:
        return []
    ingresos, base = ingresos_brutos_anio(periodo.anio)
    if ingresos is None:
        return []
    tope = tope_uvt * uvt
    actual = periodicidad_vigente(periodo.anio + 1)
    if ingresos >= tope and actual == "cuatrimestral":
        return [Resultado(clave=f"{periodo.anio}", titulo="Los ingresos superan el tope: el IVA pasaría a bimestral",
                          detalle=f"Ingresos acumulados {ingresos:,.0f} ≥ tope {tope:,.0f} ({tope_uvt} UVT).",
                          cifras={"ingresos": ingresos, "tope": tope})]
    if ingresos >= tope * Decimal("0.8") and actual == "cuatrimestral":
        return [Resultado(clave=f"{periodo.anio}", titulo="Ingresos cerca del tope de periodicidad bimestral",
                          detalle=f"Ingresos acumulados {ingresos:,.0f} equivalen al {ingresos / tope:.0%} del tope {tope:,.0f}.",
                          severidad="media", cifras={"ingresos": ingresos, "tope": tope})]
    return []


@regla("IVA004", "iva", "IVA descontable sin factura de soporte", "media", "Estatuto Tributario art. 771-2")
def descontable_sin_soporte(periodo):
    """Movimientos de IVA descontable cuyo documento no está en las facturas recibidas."""
    from contabilidad.models import movimientos_vigentes
    from facturacion.models import facturas_vigentes

    c = Calculo()
    pref = c.usar("PUC_IVA_DESCONTABLE")
    if not pref:
        return []
    from .reglas_facturas import norm_doc

    docs = {norm_doc(f.numero_completo) for f in facturas_vigentes(periodo, "recibida")}
    docs |= {norm_doc(f.numero) for f in facturas_vigentes(periodo, "recibida")}
    salida = []
    for m in movimientos_vigentes(periodo):
        if any(m.cuenta.codigo.startswith(p) for p in pref) and m.debito > TOL and norm_doc(m.documento) not in docs:
            salida.append(Resultado(
                clave=f"{m.documento or 'sin-doc'}|{m.comprobante}|{m.debito}",
                titulo=f"IVA descontable {m.debito:,.0f} sin factura DIAN",
                detalle=f"Documento {m.documento or '(vacío)'}, comprobante {m.comprobante}, tercero {m.tercero_nombre or m.nit}.",
                cifras={"iva": m.debito}))
    return salida
