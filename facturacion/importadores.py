from terceros.models import Tercero
from terceros.nit import limpiar_nit

from .models import Factura

TIPOS_TEXTO = {
    "factura": "factura", "factura electronica": "factura", "factura de venta": "factura",
    "nota credito": "nota_credito", "nota de credito": "nota_credito", "nota credito electronica": "nota_credito",
    "nota debito": "nota_debito", "nota de debito": "nota_debito",
    "documento soporte": "doc_soporte", "documento soporte en adquisiciones": "doc_soporte",
}


def _tipo(texto):
    from empresa.importacion import normalizar

    n = normalizar(texto or "")
    if not n:
        return "factura"
    for clave, valor in TIPOS_TEXTO.items():
        if clave in n:
            return valor
    return "factura"


def _tercero(nit, nombre):
    nit = limpiar_nit(nit)
    if nit:
        Tercero.objects.get_or_create(nit=nit, defaults={"razon_social": nombre or "", "origen": "factura"})
    return nit


def importar_facturas(archivo, filas):
    objetos = []
    for f in filas:
        nit_e = _tercero(f["nit_emisor"], f.get("nombre_emisor", ""))
        nit_r = _tercero(f["nit_receptor"], f.get("nombre_receptor", ""))
        tipo = f.get("tipo_documento", "")
        tipo = tipo if tipo in dict(Factura.TipoDocumento.choices) else _tipo(tipo)
        subtotal = f.get("subtotal", 0)
        total = f["total"]
        iva = f.get("iva", 0)
        if not subtotal and total:
            subtotal = total - iva
        objetos.append(
            Factura(
                periodo=archivo.periodo, archivo=archivo, sentido=archivo.sentido or "recibida",
                tipo_documento=tipo, prefijo=f.get("prefijo", ""), numero=f["numero"],
                cufe=f.get("cufe", ""), fecha=f["fecha"], nit_emisor=nit_e,
                nombre_emisor=f.get("nombre_emisor", "")[:250], nit_receptor=nit_r,
                nombre_receptor=f.get("nombre_receptor", "")[:250], subtotal=subtotal, iva=iva,
                retenciones=f.get("retenciones", 0), total=total, estado_dian=f.get("estado_dian", "")[:40],
                documento_afectado=f.get("documento_afectado", "")[:40],
            )
        )
    Factura.objects.bulk_create(objetos, batch_size=2000)
    return {"facturas": len(objetos)}
