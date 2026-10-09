from django.conf import settings
from django.db import models


class Estimacion(models.Model):
    class Escenario(models.TextChoices):
        BASE = "base", "Base"
        FAVORABLE = "favorable", "Favorable"
        ADVERSO = "adverso", "Adverso"

    impuesto = models.CharField(max_length=15)  # renta, iva, retefuente, ica
    anio = models.PositiveSmallIntegerField()
    corte = models.ForeignKey("empresa.Periodo", on_delete=models.CASCADE, related_name="estimaciones")
    escenario = models.CharField(max_length=10, choices=Escenario.choices, default=Escenario.BASE)
    valor = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    minimo = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    maximo = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    supuestos = models.JSONField(default=dict, blank=True)
    advertencias = models.JSONField(default=list, blank=True)
    calculado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("impuesto", "anio", "corte", "escenario")]
        ordering = ["impuesto", "escenario"]

    def __str__(self):
        return f"{self.impuesto} {self.anio} {self.escenario}: {self.valor}"


class Simulacion(models.Model):
    nombre = models.CharField(max_length=150)
    anio = models.PositiveSmallIntegerField()
    corte = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)
    ajustes = models.JSONField(default=dict)
    resultado = models.JSONField(default=dict)
    es_estimacion = models.BooleanField(default=True, editable=False)

    class Meta:
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.nombre} ({self.creado:%Y-%m-%d})"
