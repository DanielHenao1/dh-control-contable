from decimal import Decimal

from django.db import models


class MovimientoBanco(models.Model):
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="movimientos_banco")
    archivo = models.ForeignKey("empresa.ArchivoCargado", on_delete=models.PROTECT, related_name="movimientos_banco")
    fecha = models.DateField()
    descripcion = models.CharField(max_length=300, blank=True)
    referencia = models.CharField(max_length=60, blank=True)
    valor = models.DecimalField(max_digits=20, decimal_places=2, default=Decimal("0"))

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.fecha} {self.valor}"
