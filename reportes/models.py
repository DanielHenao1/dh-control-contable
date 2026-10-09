from django.conf import settings
from django.db import models


class InformeMensual(models.Model):
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="informes")
    generado = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    resumen = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-generado"]

    def __str__(self):
        return f"Informe {self.periodo} ({self.generado:%Y-%m-%d})"
