from django.db import models

from .nit import calcular_dv


class Tercero(models.Model):
    class TipoPersona(models.TextChoices):
        JURIDICA = "juridica", "Persona jurídica"
        NATURAL = "natural", "Persona natural"
        DESCONOCIDO = "", "Sin definir"

    nit = models.CharField("NIT / cédula (sin DV)", max_length=15, unique=True)
    dv = models.CharField("DV", max_length=1, blank=True)
    razon_social = models.CharField(max_length=250, blank=True)
    tipo_persona = models.CharField(max_length=10, choices=TipoPersona.choices, blank=True)
    regimen = models.CharField(max_length=60, blank=True)
    es_declarante = models.BooleanField("Declarante de renta", null=True, blank=True)
    es_autorretenedor = models.BooleanField(default=False)
    direccion = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    ciiu = models.CharField(max_length=6, blank=True)
    origen = models.CharField(max_length=30, blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["razon_social", "nit"]

    def __str__(self):
        return f"{self.nit}-{self.dv} {self.razon_social}".strip()

    @property
    def dv_calculado(self):
        try:
            return calcular_dv(self.nit)
        except ValueError:
            return ""

    @property
    def dv_correcto(self):
        return bool(self.dv) and self.dv == self.dv_calculado

    CAMPOS_EXOGENA = ("razon_social", "direccion", "ciudad", "tipo_persona")

    def faltantes_exogena(self):
        etiquetas = {
            "razon_social": "razón social", "direccion": "dirección",
            "ciudad": "ciudad", "tipo_persona": "tipo de persona",
        }
        return [etiquetas[c] for c in self.CAMPOS_EXOGENA if not getattr(self, c)]
