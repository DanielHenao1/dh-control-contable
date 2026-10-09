from django.db import models


class Festivo(models.Model):
    fecha = models.DateField(unique=True)
    nombre = models.CharField(max_length=100)
    origen = models.CharField(max_length=40, default="calculado", help_text="calculado (Ley 51/1983 y Pascua) o manual")

    class Meta:
        ordering = ["fecha"]

    def __str__(self):
        return f"{self.fecha} {self.nombre}"


class ReglaVencimiento(models.Model):
    """Regla de vencimiento: día hábil n según el último dígito del NIT, o fecha fija publicada.

    Solo existen las reglas que se pudieron verificar. No se inventan días para otros dígitos.
    """

    class Modo(models.TextChoices):
        DIA_HABIL = "dia_habil", "Día hábil n del mes de vencimiento (según último dígito del NIT)"
        FECHA_FIJA = "fecha_fija", "Fecha fija del calendario"

    class Verificacion(models.TextChoices):
        DOS_FUENTES = "dos_fuentes", "Dos fuentes coinciden"
        REGLA = "regla", "Calculada con la regla del decreto (sin lista oficial contrastada)"
        UNA_FUENTE = "una_fuente", "Una fuente secundaria"
        ESTIMADA = "estimada", "Estimada por la regla (no hay lista oficial aún)"
        NO_VERIFICADA = "no_verificada", "No verificada"

    obligacion = models.CharField(max_length=30)  # retefuente, iva, ica, renta_c1, renta_c2, exogena, rub, matricula
    modo = models.CharField(max_length=12, choices=Modo.choices)
    digito = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Último dígito del NIT (modo día hábil)")
    dia_habil = models.PositiveSmallIntegerField(null=True, blank=True)
    fecha = models.DateField(null=True, blank=True, help_text="Solo para fecha fija")
    periodo_clave = models.CharField(max_length=30, blank=True, help_text="Solo fecha fija: 2026-B5, 2026-anual...")
    descripcion = models.CharField(max_length=200, blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    verificacion = models.CharField(max_length=15, choices=Verificacion.choices, default=Verificacion.NO_VERIFICADA)
    fuente = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ["obligacion", "vigente_desde", "fecha"]

    def __str__(self):
        if self.modo == self.Modo.DIA_HABIL:
            return f"{self.obligacion} dígito {self.digito} → día hábil {self.dia_habil}"
        return f"{self.obligacion} {self.periodo_clave} → {self.fecha}"


class Obligacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_PREPARACION = "en_preparacion", "En preparación"
        PRESENTADA = "presentada", "Presentada"
        PAGADA = "pagada", "Presentada y pagada"

    tipo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=200)
    periodo_texto = models.CharField(max_length=60, blank=True)
    clave = models.CharField(max_length=60, help_text="Identificador único del período, ej. 2026-09")
    fecha_limite = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    verificacion = models.CharField(max_length=15, choices=ReglaVencimiento.Verificacion.choices, default="no_verificada")
    fuente = models.CharField(max_length=400, blank=True)
    laboral = models.BooleanField(default=False, help_text="Fecha laboral/mercantil, no tributaria")
    elabora = models.CharField(max_length=120, blank=True)
    revisa = models.CharField(max_length=120, blank=True)
    firma = models.CharField(max_length=120, blank=True)
    evidencia = models.ForeignKey(
        "empresa.ArchivoCargado", null=True, blank=True, on_delete=models.SET_NULL, related_name="obligaciones"
    )
    notas = models.TextField(blank=True)
    ultima_alerta = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [("tipo", "clave")]
        ordering = ["fecha_limite", "tipo"]

    def __str__(self):
        return f"{self.nombre} {self.periodo_texto} ({self.fecha_limite or 'sin fecha'})"

    @property
    def cumplida(self):
        return self.estado in (self.Estado.PRESENTADA, self.Estado.PAGADA)
