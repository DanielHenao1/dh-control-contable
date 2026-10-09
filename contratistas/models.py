from datetime import timedelta

from django.db import models


class Contratista(models.Model):
    nombre = models.CharField(max_length=150)
    nit = models.CharField(max_length=20, blank=True)
    contrato = models.CharField(max_length=40, blank=True)
    inicio = models.DateField(null=True, blank=True)
    fin = models.DateField(null=True, blank=True)
    honorarios_mensuales = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    honorarios_mas_iva = models.BooleanField(default=True)
    alcance = models.TextField(blank=True)
    exclusiones = models.TextField(blank=True)
    dias_informe = models.PositiveSmallIntegerField(default=15, help_text="Días para entregar el informe después de la entrega mensual")

    def __str__(self):
        return f"{self.nombre} · {self.contrato}"

    @property
    def vigente(self):
        from django.utils import timezone

        hoy = timezone.localdate()
        return bool(self.inicio and self.fin and self.inicio <= hoy <= self.fin)

    @property
    def honorarios_con_iva(self):
        if self.honorarios_mensuales is None:
            return None
        return self.honorarios_mensuales  # el IVA se parametriza aparte; no se asume tarifa aquí


class Entrega(models.Model):
    """Entrega mensual de la empresa al contratista (exportes y soportes)."""

    contratista = models.ForeignKey(Contratista, on_delete=models.CASCADE, related_name="entregas")
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT)
    descripcion = models.CharField(max_length=250, blank=True)
    entregada_el = models.DateField()
    archivos = models.ManyToManyField("empresa.ArchivoCargado", blank=True)

    class Meta:
        ordering = ["-entregada_el"]
        unique_together = [("contratista", "periodo")]

    def __str__(self):
        return f"{self.contratista.nombre} · {self.periodo}"

    @property
    def fecha_limite_informe(self):
        return self.entregada_el + timedelta(days=self.contratista.dias_informe)

    @property
    def informe(self):
        return self.informes.order_by("-recibido_el").first()

    @property
    def informe_atrasado(self):
        from django.utils import timezone

        return self.informe is None and timezone.localdate() > self.fecha_limite_informe


class InformeContratista(models.Model):
    entrega = models.ForeignKey(Entrega, on_delete=models.CASCADE, related_name="informes")
    recibido_el = models.DateField()
    resumen = models.TextField(blank=True)
    archivo = models.ForeignKey("empresa.ArchivoCargado", null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Informe {self.entrega} ({self.recibido_el})"


class Observacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        RESPONDIDA = "respondida", "Respondida"
        CERRADA = "cerrada", "Cerrada"

    contratista = models.ForeignKey(Contratista, on_delete=models.CASCADE, related_name="observaciones")
    informe = models.ForeignKey(InformeContratista, null=True, blank=True, on_delete=models.SET_NULL, related_name="observaciones")
    texto = models.TextField()
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    respuesta = models.TextField(blank=True)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["estado", "-creada"]

    def __str__(self):
        return self.texto[:60]
