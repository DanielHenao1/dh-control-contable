from django.db import models


class ExplicacionIA(models.Model):
    """Texto redactado por el asistente para un hallazgo. Nunca contiene cifras nuevas."""

    hallazgo = models.OneToOneField("controles.Hallazgo", on_delete=models.CASCADE, related_name="explicacion_ia")
    texto = models.TextField()
    modelo = models.CharField(max_length=60, blank=True)
    generado = models.DateTimeField(auto_now=True)
