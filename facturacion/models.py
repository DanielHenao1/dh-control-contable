from decimal import Decimal

from django.db import models

CERO = Decimal("0")


class Factura(models.Model):
    class Sentido(models.TextChoices):
        EMITIDA = "emitida", "Emitida (ventas)"
        RECIBIDA = "recibida", "Recibida (compras)"

    class TipoDocumento(models.TextChoices):
        FACTURA = "factura", "Factura"
        NOTA_CREDITO = "nota_credito", "Nota crédito"
        NOTA_DEBITO = "nota_debito", "Nota débito"
        DOC_SOPORTE = "doc_soporte", "Documento soporte"

    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="facturas")
    archivo = models.ForeignKey("empresa.ArchivoCargado", on_delete=models.PROTECT, related_name="facturas")
    sentido = models.CharField(max_length=10, choices=Sentido.choices)
    tipo_documento = models.CharField(max_length=15, choices=TipoDocumento.choices, default=TipoDocumento.FACTURA)
    prefijo = models.CharField(max_length=10, blank=True)
    numero = models.CharField(max_length=30)
    cufe = models.CharField(max_length=130, blank=True)
    fecha = models.DateField()
    nit_emisor = models.CharField(max_length=15)
    nombre_emisor = models.CharField(max_length=250, blank=True)
    nit_receptor = models.CharField(max_length=15)
    nombre_receptor = models.CharField(max_length=250, blank=True)
    subtotal = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    iva = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    retenciones = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    total = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    estado_dian = models.CharField(max_length=40, blank=True)
    documento_afectado = models.CharField(max_length=40, blank=True, help_text="Factura que corrige una nota crédito/débito")

    class Meta:
        ordering = ["fecha", "prefijo", "numero"]
        indexes = [models.Index(fields=["periodo", "sentido"])]

    def __str__(self):
        return f"{self.numero_completo} {self.fecha}"

    @property
    def numero_completo(self):
        return f"{self.prefijo}{self.numero}"

    @property
    def nit_tercero(self):
        return self.nit_emisor if self.sentido == self.Sentido.RECIBIDA else self.nit_receptor

    @property
    def es_nota_credito(self):
        return self.tipo_documento == self.TipoDocumento.NOTA_CREDITO

    @property
    def signo(self):
        return Decimal("-1") if self.es_nota_credito else Decimal("1")


def facturas_vigentes(periodo=None, sentido=None):
    q = Factura.objects.filter(archivo__vigente=True)
    if periodo is not None:
        q = q.filter(periodo=periodo)
    if sentido:
        q = q.filter(sentido=sentido)
    return q
