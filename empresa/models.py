import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from .permisos import tiene_permiso


class ParametroPendiente(Exception):
    """El parámetro no existe, está vacío o no hay uno vigente para la fecha."""

    def __init__(self, codigo, fecha=None):
        self.codigo = codigo
        self.fecha = fecha
        super().__init__(f"Parámetro pendiente: {codigo}" + (f" ({fecha})" if fecha else ""))


class PeriodoCerrado(Exception):
    pass


class Usuario(AbstractUser):
    class Rol(models.TextChoices):
        DUENO = "dueno", "Dueño / administrador"
        CONTADOR = "contador", "Contador o revisor (solo lectura)"
        ASISTENTE = "asistente", "Asistente de carga"
        CONSULTA = "consulta", "Consulta"
        CONTRATISTA = "contratista", "Contratista (acceso limitado)"

    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CONSULTA)

    def puede(self, permiso):
        return tiene_permiso(self, permiso)

    @property
    def nombre_visible(self):
        return self.get_full_name() or self.username


class Empresa(models.Model):
    nit = models.CharField("NIT (sin DV)", max_length=15, unique=True)
    dv = models.CharField("DV", max_length=1)
    razon_social = models.CharField(max_length=200)
    domicilio = models.CharField(max_length=120, blank=True)
    representante_legal = models.CharField(max_length=120, blank=True)
    revisor_fiscal = models.CharField(max_length=120, blank=True)
    contador = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name_plural = "empresa"

    @property
    def ultimo_digito(self):
        return int(self.nit[-1])

    @property
    def nit_formateado(self):
        n = self.nit
        grupos = []
        while n:
            grupos.insert(0, n[-3:])
            n = n[:-3]
        return ".".join(grupos) + f"-{self.dv}"

    def __str__(self):
        return f"{self.razon_social} ({self.nit_formateado})"

    @classmethod
    def actual(cls):
        return cls.objects.first()


class Periodo(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        EN_REVISION = "en_revision", "En revisión"
        CERRADO = "cerrado", "Cerrado"

    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField()
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.ABIERTO)

    class Meta:
        unique_together = [("anio", "mes")]
        ordering = ["-anio", "-mes"]

    def __str__(self):
        return f"{self.anio}-{self.mes:02d}"

    @classmethod
    def obtener(cls, anio, mes):
        return cls.objects.get_or_create(anio=anio, mes=mes)[0]

    @property
    def cerrado(self):
        return self.estado == self.Estado.CERRADO

    def verificar_abierto(self):
        if self.cerrado:
            raise PeriodoCerrado(f"El periodo {self} está cerrado y no se puede modificar.")

    @property
    def fin(self):
        import calendar

        return date(self.anio, self.mes, calendar.monthrange(self.anio, self.mes)[1])

    @property
    def inicio(self):
        return date(self.anio, self.mes, 1)

    def anterior(self):
        return (self.anio - 1, 12) if self.mes == 1 else (self.anio, self.mes - 1)


class Parametro(models.Model):
    """Valor tributario/operativo con vigencia. Nada de esto va fijo en el código."""

    class Tipo(models.TextChoices):
        DECIMAL = "decimal", "Decimal"
        ENTERO = "entero", "Entero"
        TEXTO = "texto", "Texto"
        LISTA = "lista", "Lista (separada por comas)"

    class Estado(models.TextChoices):
        VERIFICADO = "verificado", "Verificado"
        POR_VERIFICAR = "por_verificar", "Por verificar"

    codigo = models.CharField(max_length=60)
    descripcion = models.CharField(max_length=250, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.DECIMAL)
    valor = models.TextField(blank=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.POR_VERIFICAR)
    fuente = models.CharField(max_length=300, blank=True)

    class Meta:
        unique_together = [("codigo", "vigente_desde")]
        ordering = ["codigo", "-vigente_desde"]

    def __str__(self):
        return f"{self.codigo} = {self.valor or '(vacío)'} desde {self.vigente_desde}"

    @property
    def pendiente(self):
        return self.estado != self.Estado.VERIFICADO or not self.valor.strip()

    def convertido(self):
        v = self.valor.strip()
        if self.tipo == self.Tipo.DECIMAL:
            try:
                return Decimal(v.replace(",", "."))
            except InvalidOperation as exc:
                raise ParametroPendiente(self.codigo) from exc
        if self.tipo == self.Tipo.ENTERO:
            return int(v)
        if self.tipo == self.Tipo.LISTA:
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @classmethod
    def vigente(cls, codigo, fecha=None):
        fecha = fecha or timezone.localdate()
        return (
            cls.objects.filter(codigo=codigo, vigente_desde__lte=fecha)
            .filter(models.Q(vigente_hasta__isnull=True) | models.Q(vigente_hasta__gte=fecha))
            .order_by("-vigente_desde")
            .first()
        )

    @classmethod
    def obtener(cls, codigo, fecha=None):
        """Devuelve el valor tipado. Levanta ParametroPendiente si falta o está vacío."""
        p = cls.vigente(codigo, fecha)
        if p is None or not p.valor.strip():
            raise ParametroPendiente(codigo, fecha)
        return p.convertido()

    @classmethod
    def obtener_con_aviso(cls, codigo, fecha=None):
        """(valor, aviso). El aviso es un texto si el parámetro sigue 'por verificar'."""
        p = cls.vigente(codigo, fecha)
        if p is None or not p.valor.strip():
            raise ParametroPendiente(codigo, fecha)
        aviso = f"{codigo} está por verificar" if p.estado != cls.Estado.VERIFICADO else None
        return p.convertido(), aviso

    @classmethod
    def obtener_o(cls, codigo, defecto=None, fecha=None):
        try:
            return cls.obtener(codigo, fecha)
        except ParametroPendiente:
            return defecto


class PerfilImportacion(models.Model):
    """Mapeo de columnas configurable desde la interfaz, para adaptar los exportes reales."""

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20)  # clave de importacion.CAMPOS_POR_TIPO
    hoja = models.CharField(max_length=60, blank=True, help_text="Vacío = primera hoja")
    fila_encabezado = models.PositiveSmallIntegerField(default=1)
    separador_csv = models.CharField(max_length=3, default=",")
    decimal_coma = models.BooleanField(
        "Decimales con coma (1.234,56)", default=False,
        help_text="Marcar si el archivo usa punto para miles y coma para decimales.",
    )
    formato_fecha = models.CharField(max_length=20, blank=True, help_text="Ej. %d/%m/%Y. Vacío = automático")
    mapeo = models.JSONField(default=dict, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        unique_together = [("nombre", "tipo")]
        ordering = ["tipo", "nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"


def ruta_carga(instancia, nombre):
    return f"cargas/{instancia.hash_sha256[:2]}/{instancia.hash_sha256}-{nombre}"


class ArchivoCargado(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de confirmar"
        IMPORTADO = "importado", "Importado"
        ERROR = "error", "Con errores"

    class Tipo(models.TextChoices):
        BALANCE = "balance", "Balance de prueba (World Office)"
        AUXILIAR = "auxiliar", "Auxiliares (World Office)"
        FACTURAS_DIAN = "facturas_dian", "Facturas electrónicas (Excel DIAN)"
        FACTURAS_XML = "facturas_xml", "Facturas electrónicas (XML)"
        RETENCIONES = "retenciones", "Retenciones practicadas"
        EXTRACTO_BANCO = "extracto_banco", "Extracto bancario"
        DECLARACION = "declaracion", "Declaración / borrador del contratista"
        OTRO = "otro", "Otro soporte"

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    archivo = models.FileField(upload_to=ruta_carga, max_length=300)
    nombre_original = models.CharField(max_length=255)
    hash_sha256 = models.CharField(max_length=64, db_index=True)
    tamano = models.PositiveBigIntegerField(default=0)
    origen = models.CharField(max_length=60, blank=True)
    sentido = models.CharField(max_length=10, blank=True)  # emitida / recibida (facturas)
    periodo = models.ForeignKey(Periodo, null=True, blank=True, on_delete=models.PROTECT, related_name="archivos")
    perfil = models.ForeignKey(PerfilImportacion, null=True, blank=True, on_delete=models.SET_NULL)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    vigente = models.BooleanField(default=False)
    resumen = models.JSONField(default=dict, blank=True)
    errores = models.JSONField(default=list, blank=True)
    formulario = models.CharField(max_length=10, blank=True)  # declaraciones: 300, 350, 110, ica, otro
    verificaciones = models.JSONField(default=dict, blank=True)  # avisos de la revisión previa y si se forzó

    class Meta:
        ordering = ["-creado"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "hash_sha256"], name="archivo_unico_por_tipo_hash"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.nombre_original}"

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.only("hash_sha256", "archivo").get(pk=self.pk)
            if original.hash_sha256 != self.hash_sha256 or original.archivo.name != self.archivo.name:
                raise ValueError("Un archivo cargado no se sobrescribe ni se reemplaza.")
        super().save(*args, **kwargs)

    @staticmethod
    def calcular_hash(contenido: bytes) -> str:
        return hashlib.sha256(contenido).hexdigest()

    def marcar_vigente(self):
        """El último archivo importado del mismo tipo/periodo/sentido es el vigente; los previos se conservan."""
        grupo = {"facturas_dian", "facturas_xml"}
        tipos = grupo if self.tipo in grupo else {self.tipo}
        type(self).objects.filter(
            tipo__in=tipos, periodo=self.periodo, sentido=self.sentido, vigente=True
        ).exclude(pk=self.pk).update(vigente=False)
        self.vigente = True
        self.save(update_fields=["vigente"])


class RegistroAuditoria(models.Model):
    """Bitácora de solo inserción: quién hizo qué y cuándo (incluye lecturas sensibles)."""

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    usuario_texto = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=30)  # crear, modificar, eliminar, lectura, login, descarga, cierre
    modelo = models.CharField(max_length=80, blank=True)
    objeto_id = models.CharField(max_length=60, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    detalle = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    fecha = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.fecha:%Y-%m-%d %H:%M} {self.usuario_texto} {self.accion} {self.modelo}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("El registro de auditoría no se modifica.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("El registro de auditoría no se elimina.")

    @classmethod
    def registrar(cls, accion, objeto=None, descripcion="", detalle=None, usuario=None, ip=None, modelo="", objeto_id=""):
        from .middleware import usuario_actual

        usuario = usuario or usuario_actual()
        if usuario is not None and not getattr(usuario, "pk", None):
            usuario = None
        if objeto is not None:
            modelo = modelo or objeto._meta.label
            objeto_id = objeto_id or str(objeto.pk)
        return cls.objects.create(
            usuario=usuario,
            usuario_texto=getattr(usuario, "username", "sistema") if usuario else "sistema",
            accion=accion,
            modelo=modelo,
            objeto_id=objeto_id,
            descripcion=descripcion[:300],
            detalle=json.loads(json.dumps(detalle or {}, default=str)),
            ip=ip,
        )
