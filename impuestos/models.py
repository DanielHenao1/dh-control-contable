from decimal import Decimal

from django.conf import settings
from django.db import models

CERO = Decimal("0")


class ConceptoRetencion(models.Model):
    """Concepto con su base mínima en UVT y tarifa, con vigencia. Se carga con datos verificados."""

    class Estado(models.TextChoices):
        VERIFICADO = "verificado", "Verificado"
        POR_VERIFICAR = "por_verificar", "Por verificar"

    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    base_minima_uvt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tarifa_declarante = models.DecimalField("Tarifa (%) tercero declarante", max_digits=6, decimal_places=3, null=True, blank=True)
    tarifa_no_declarante = models.DecimalField("Tarifa (%) no declarante", max_digits=6, decimal_places=3, null=True, blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.POR_VERIFICAR)
    fuente = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("codigo", "vigente_desde")]
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} {self.nombre}"

    @classmethod
    def vigente(cls, codigo, fecha):
        return (
            cls.objects.filter(codigo=codigo, vigente_desde__lte=fecha)
            .filter(models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha))
            .order_by("-vigente_desde")
            .first()
        )

    def tarifa_para(self, declarante):
        """Tarifa en % según la condición del tercero; None si no está cargada."""
        if declarante is False and self.tarifa_no_declarante is not None:
            return self.tarifa_no_declarante
        return self.tarifa_declarante


class Retencion(models.Model):
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="retenciones")
    archivo = models.ForeignKey("empresa.ArchivoCargado", on_delete=models.PROTECT, related_name="retenciones")
    fecha = models.DateField()
    documento = models.CharField(max_length=60, blank=True)
    nit = models.CharField(max_length=15)
    concepto = models.CharField(max_length=30)
    base = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    tarifa_aplicada = models.DecimalField(max_digits=7, decimal_places=3, default=CERO, help_text="En %")
    retenido = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    teorico = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.fecha} {self.nit} {self.concepto} {self.retenido}"


class Declaracion(models.Model):
    class Tipo(models.TextChoices):
        RETEFUENTE = "retefuente", "Retención en la fuente"
        IVA = "iva", "IVA"
        ICA = "ica", "ICA Bogotá"
        RETEICA = "reteica", "ReteICA Bogotá"
        RENTA = "renta", "Renta y complementarios"
        EXOGENA = "exogena", "Información exógena nacional (DIAN)"
        EXOGENA_DISTRITAL = "exogena_distrital", "Información exógena distrital (Bogotá)"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador propio"
        PRESENTADA = "presentada", "Presentada"
        PAGADA = "pagada", "Pagada"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    anio = models.PositiveSmallIntegerField()
    indice = models.PositiveSmallIntegerField(
        default=1, help_text="Mes (retención), cuatrimestre/bimestre (IVA, ICA) o 1 (renta)"
    )
    formulario = models.CharField(max_length=30, blank=True)
    valor_propio = models.DecimalField("Valor calculado por el sistema", max_digits=20, decimal_places=2, null=True, blank=True)
    valor_declarado = models.DecimalField("Valor declarado por el contratista", max_digits=20, decimal_places=2, null=True, blank=True)
    detalle_propio = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.BORRADOR)
    elabora = models.CharField(max_length=120, blank=True)
    revisa = models.CharField(max_length=120, blank=True)
    firma = models.CharField(max_length=120, blank=True)
    presentada_el = models.DateField(null=True, blank=True)
    evidencia = models.ForeignKey(
        "empresa.ArchivoCargado", null=True, blank=True, on_delete=models.SET_NULL, related_name="declaraciones"
    )
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("tipo", "anio", "indice")]
        ordering = ["-anio", "tipo", "-indice"]

    def __str__(self):
        return f"{self.get_tipo_display()} {self.anio}-{self.indice}"

    @property
    def diferencia(self):
        if self.valor_propio is None or self.valor_declarado is None:
            return None
        return self.valor_propio - self.valor_declarado


class DiferenciaFiscal(models.Model):
    """Diferencia contable-fiscal para la conciliación de renta."""

    class Tipo(models.TextChoices):
        PERMANENTE_MAS = "perm_mas", "Permanente que aumenta la renta (gasto no deducible, etc.)"
        PERMANENTE_MENOS = "perm_menos", "Permanente que disminuye la renta (ingreso no constitutivo, etc.)"
        TEMPORAL_MAS = "temp_mas", "Temporal que aumenta la renta"
        TEMPORAL_MENOS = "temp_menos", "Temporal que disminuye la renta"

    anio = models.PositiveSmallIntegerField()
    concepto = models.CharField(max_length=200)
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=20, decimal_places=2)
    soporte = models.CharField(max_length=300, blank=True, help_text="Norma o soporte que justifica la diferencia")
    explicada = models.BooleanField(default=False)
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        ordering = ["anio", "concepto"]

    def __str__(self):
        return f"{self.anio} {self.concepto}"

    @property
    def efecto(self):
        """Efecto firmado sobre la renta líquida."""
        return self.valor if self.tipo.endswith("_mas") else -self.valor


class TarifaICA(models.Model):
    """Tarifa de ICA por actividad (CIIU), en por mil. Se carga verificada por el contador."""

    ciiu = models.CharField(max_length=6)
    descripcion = models.CharField(max_length=250, blank=True)
    tarifa_por_mil = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, default="por_verificar")
    fuente = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("ciiu", "vigente_desde")]
        ordering = ["ciiu"]

    def __str__(self):
        return f"{self.ciiu} {self.tarifa_por_mil}‰"
