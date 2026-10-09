from django.conf import settings
from django.db import models


class ReglaControl(models.Model):
    class Severidad(models.TextChoices):
        ALTA = "alta", "Alta (rojo)"
        MEDIA = "media", "Media (ámbar)"
        BAJA = "baja", "Baja (verde)"

    codigo = models.CharField(max_length=40, unique=True)
    grupo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    severidad = models.CharField(max_length=6, choices=Severidad.choices, default=Severidad.MEDIA)
    norma = models.CharField(max_length=300, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["grupo", "codigo"]

    def __str__(self):
        return f"{self.codigo} {self.nombre}"


class Hallazgo(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        EXPLICADO = "explicado", "Explicado"
        CORREGIDO = "corregido", "Corregido"

    regla = models.ForeignKey(ReglaControl, on_delete=models.PROTECT, related_name="hallazgos")
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="hallazgos")
    clave = models.CharField(max_length=200, help_text="Identifica el registro afectado; permite no duplicar")
    titulo = models.CharField(max_length=250)
    detalle = models.TextField(blank=True)
    severidad = models.CharField(max_length=6, choices=ReglaControl.Severidad.choices)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTO)
    explicacion = models.TextField(blank=True)
    cifras = models.JSONField(default=dict, blank=True)
    evidencia = models.JSONField(default=dict, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    resuelto_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    detectado_ultima_vez = models.BooleanField(default=True)

    class Meta:
        unique_together = [("regla", "periodo", "clave")]
        ordering = ["estado", "severidad", "-actualizado"]

    def __str__(self):
        return f"[{self.regla.codigo}] {self.titulo}"

    @property
    def semaforo(self):
        return {"alta": "rojo", "media": "ambar", "baja": "verde"}[self.severidad]
