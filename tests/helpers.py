"""Datos sintéticos para las pruebas. Nada de esto es información real."""
import uuid
from datetime import date
from decimal import Decimal

from contabilidad.models import Cuenta, Movimiento, SaldoCuenta
from empresa.models import ArchivoCargado, Periodo
from facturacion.models import Factura
from impuestos.models import Retencion


def D(x):
    return Decimal(str(x))


def archivo(tipo, periodo, sentido=""):
    return ArchivoCargado.objects.create(
        tipo=tipo, nombre_original=f"{tipo}.xlsx", hash_sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        periodo=periodo, sentido=sentido, estado="importado", vigente=True, archivo=f"cargas/x/{tipo}.xlsx",
    )


def balance(periodo, filas):
    """filas: (codigo, nombre, saldo_inicial, debito, credito, saldo_final)"""
    a = archivo("balance", periodo)
    for codigo, nombre, ini, deb, cre, fin in filas:
        c, _ = Cuenta.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
        SaldoCuenta.objects.create(periodo=periodo, archivo=a, cuenta=c, saldo_inicial=D(ini), debito=D(deb), credito=D(cre), saldo_final=D(fin))
    return a


def auxiliar(periodo, filas):
    """filas: (fecha, comprobante, documento, cuenta, nit, debito, credito)"""
    a = archivo("auxiliar", periodo)
    for fecha, comp, doc, cuenta, nit, deb, cre in filas:
        c, _ = Cuenta.objects.get_or_create(codigo=cuenta)
        Movimiento.objects.create(periodo=periodo, archivo=a, fecha=fecha, comprobante=comp, documento=doc, cuenta=c, nit=nit, debito=D(deb), credito=D(cre))
    return a


def factura(periodo, sentido, numero, fecha, nit_e, nit_r, subtotal, iva, prefijo="", tipo="factura", a=None, **kw):
    a = a or archivo("facturas_dian", periodo, sentido)
    return Factura.objects.create(
        periodo=periodo, archivo=a, sentido=sentido, tipo_documento=tipo, prefijo=prefijo, numero=numero, fecha=fecha,
        nit_emisor=nit_e, nit_receptor=nit_r, subtotal=D(subtotal), iva=D(iva), total=D(subtotal) + D(iva), **kw,
    )


def retencion(periodo, fecha, nit, concepto, base, tarifa, retenido, doc="DOC1", a=None):
    a = a or archivo("retenciones", periodo)
    return Retencion.objects.create(periodo=periodo, archivo=a, fecha=fecha, documento=doc, nit=nit, concepto=concepto,
                                    base=D(base), tarifa_aplicada=D(tarifa), retenido=D(retenido))


def periodo(anio=2026, mes=9):
    return Periodo.obtener(anio, mes)


__all__ = ["D", "date", "archivo", "balance", "auxiliar", "factura", "retencion", "periodo"]
