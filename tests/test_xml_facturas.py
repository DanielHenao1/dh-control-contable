from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from empresa import cargas
from empresa.models import Periodo
from facturacion.models import Factura
from facturacion.xml import parsear_archivo, parsear_xml

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
 <cbc:ID>SETP990000123</cbc:ID>
 <cbc:UUID>abc123cufe</cbc:UUID>
 <cbc:IssueDate>2026-09-15</cbc:IssueDate>
 <cac:AccountingSupplierParty><cac:Party><cac:PartyTaxScheme>
   <cbc:RegistrationName>Proveedor Sintético SAS</cbc:RegistrationName><cbc:CompanyID>900123456</cbc:CompanyID>
 </cac:PartyTaxScheme></cac:Party></cac:AccountingSupplierParty>
 <cac:AccountingCustomerParty><cac:Party><cac:PartyTaxScheme>
   <cbc:RegistrationName>DH TRANS-STORAGE SAS</cbc:RegistrationName><cbc:CompanyID>900902549</cbc:CompanyID>
 </cac:PartyTaxScheme></cac:Party></cac:AccountingCustomerParty>
 <cac:TaxTotal><cbc:TaxAmount>190.00</cbc:TaxAmount><cac:TaxSubtotal><cac:TaxCategory><cac:TaxScheme><cbc:ID>01</cbc:ID></cac:TaxScheme></cac:TaxCategory></cac:TaxSubtotal></cac:TaxTotal>
 <cac:LegalMonetaryTotal><cbc:LineExtensionAmount>1000.00</cbc:LineExtensionAmount><cbc:PayableAmount>1190.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
</Invoice>""".encode()

NOTA = XML.replace(b"<Invoice", b"<CreditNote").replace(b"</Invoice>", b"</CreditNote>").replace(b"SETP990000123", b"NC77")


def test_parsear_factura():
    f = parsear_xml(XML)
    assert f["prefijo"] == "SETP" and f["numero"] == "990000123" and f["fecha"] == date(2026, 9, 15)
    assert f["nit_emisor"] == "900123456" and f["nit_receptor"] == "900902549"
    assert f["subtotal"] == Decimal("1000.00") and f["iva"] == Decimal("190.00") and f["total"] == Decimal("1190.00")
    assert f["tipo_documento"] == "factura" and f["cufe"] == "abc123cufe"


def test_nota_credito():
    assert parsear_xml(NOTA)["tipo_documento"] == "nota_credito"


def test_attached_document():
    envuelto = (
        '<?xml version="1.0"?><AttachedDocument xmlns="urn:oasis:names:specification:ubl:schema:xsd:AttachedDocument-2" '
        'xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"><cbc:Description><![CDATA['
        + XML.decode() + "]]></cbc:Description></AttachedDocument>"
    ).encode()
    assert parsear_xml(envuelto)["numero"] == "990000123"


def test_zip_con_un_xml_malo():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.xml", XML)
        z.writestr("b.xml", b"<Basura/>")
    filas, errores = parsear_archivo(buf.getvalue(), "lote.zip")
    assert len(filas) == 1 and len(errores) == 1


@pytest.mark.django_db
def test_importar_xml(dueno):
    p = Periodo.obtener(2026, 9)
    a = cargas.registrar_archivo(SimpleUploadedFile("f.xml", XML), "facturas_xml", p, dueno, sentido="recibida")
    a = cargas.confirmar(a, dueno)
    assert a.estado == "importado"
    f = Factura.objects.get()
    assert f.sentido == "recibida" and f.numero_completo == "SETP990000123"
