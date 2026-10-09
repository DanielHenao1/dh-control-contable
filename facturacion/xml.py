"""Lectura de facturas electrónicas UBL 2.1 (XML de la DIAN) con lxml, sin depender de prefijos."""
import io
import re
import zipfile
from datetime import date
from decimal import Decimal

from lxml import etree

# Parser endurecido: sin entidades externas, sin red, sin DTD (evita XXE y "billion laughs")
PARSER = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, dtd_validation=False, huge_tree=False)
MAX_XML_BYTES = 5 * 1024 * 1024
MAX_ZIP_TOTAL = 200 * 1024 * 1024


def _fromstring(data):
    if len(data) > MAX_XML_BYTES:
        raise ValueError("XML demasiado grande")
    return etree.fromstring(data, PARSER)


def _t(nodo, ruta):
    r = nodo.xpath(ruta)
    return (r[0].text or "").strip() if r else ""


def _d(nodo, ruta):
    v = _t(nodo, ruta)
    return Decimal(v) if v else Decimal("0")


def _local(nombre):
    return f"*[local-name()='{nombre}']"


def _parte(raiz, rol):
    base = f".//{_local(rol)}//{_local('PartyTaxScheme')}"
    nit = _t(raiz, f"{base}/{_local('CompanyID')}")
    nombre = _t(raiz, f"{base}/{_local('RegistrationName')}")
    if not nit:
        nit = _t(raiz, f".//{_local(rol)}//{_local('PartyLegalEntity')}/{_local('CompanyID')}")
    return re.sub(r"\D", "", nit), nombre


def _documento_interno(raiz):
    """Los XML 'AttachedDocument' de la DIAN traen la factura dentro de cbc:Description."""
    if etree.QName(raiz).localname != "AttachedDocument":
        return raiz
    for d in raiz.xpath(f".//{_local('Description')}"):
        texto = (d.text or "").strip()
        if texto.startswith("<?xml") or "<Invoice" in texto or "<CreditNote" in texto or "<DebitNote" in texto:
            return _fromstring(texto.encode())
    return raiz


TIPOS = {"Invoice": "factura", "CreditNote": "nota_credito", "DebitNote": "nota_debito"}


def parsear_xml(contenido: bytes):
    raiz = _documento_interno(_fromstring(contenido))
    local = etree.QName(raiz).localname
    if local not in TIPOS:
        raise ValueError(f"XML no reconocido como factura electrónica ({local})")
    numero_completo = _t(raiz, f"./{_local('ID')}")
    m = re.match(r"^([A-Za-z]*)(\d+)$", numero_completo)
    prefijo, numero = (m.group(1), m.group(2)) if m else ("", numero_completo)
    nit_e, nom_e = _parte(raiz, "AccountingSupplierParty")
    nit_r, nom_r = _parte(raiz, "AccountingCustomerParty")
    iva = Decimal("0")
    for tt in raiz.xpath(f"./{_local('TaxTotal')}"):
        esquema = _t(tt, f".//{_local('TaxScheme')}/{_local('ID')}")
        if esquema in ("01", ""):
            iva += _d(tt, f"./{_local('TaxAmount')}")
    monetario = f"./{_local('LegalMonetaryTotal')}"
    afectado = _t(raiz, f".//{_local('BillingReference')}//{_local('InvoiceDocumentReference')}/{_local('ID')}")
    return {
        "tipo_documento": TIPOS[local],
        "prefijo": prefijo,
        "numero": numero,
        "cufe": _t(raiz, f"./{_local('UUID')}"),
        "fecha": date.fromisoformat(_t(raiz, f"./{_local('IssueDate')}")),
        "nit_emisor": nit_e, "nombre_emisor": nom_e,
        "nit_receptor": nit_r, "nombre_receptor": nom_r,
        "subtotal": _d(raiz, f"{monetario}/{_local('LineExtensionAmount')}"),
        "iva": iva,
        "retenciones": Decimal("0"),
        "total": _d(raiz, f"{monetario}/{_local('PayableAmount')}"),
        "estado_dian": "",
        "documento_afectado": afectado,
    }


def parsear_archivo(contenido: bytes, nombre: str):
    """Acepta un XML o un .zip con varios XML. Devuelve (filas, errores)."""
    filas, errores = [], []
    if nombre.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_ZIP_TOTAL:
                raise ValueError("El .zip descomprimido es demasiado grande")
            items = [(n, z.read(n)) for n in z.namelist() if n.lower().endswith(".xml")]
    else:
        items = [(nombre, contenido)]
    for i, (n, data) in enumerate(items, start=1):
        try:
            filas.append(parsear_xml(data))
        except Exception as exc:  # un XML malo no frena los demás
            errores.append({"fila": i, "problemas": [f"{n}: {exc}"]})
    return filas, errores
