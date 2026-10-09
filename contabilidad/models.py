from decimal import Decimal

from django.db import models

CERO = Decimal("0")


class Cuenta(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} {self.nombre}"

    @property
    def clase(self):
        return self.codigo[:1]

    @property
    def naturaleza(self):
        """'D' (débito) para activos, gastos, costos; 'C' para pasivo, patrimonio, ingresos."""
        return "C" if self.clase in ("2", "3", "4") else "D"


class SaldoCuenta(models.Model):
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="saldos")
    archivo = models.ForeignKey("empresa.ArchivoCargado", on_delete=models.PROTECT, related_name="saldos")
    cuenta = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name="saldos")
    saldo_inicial = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    debito = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    credito = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    saldo_final = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)

    class Meta:
        indexes = [models.Index(fields=["periodo", "cuenta"])]
        unique_together = [("archivo", "cuenta")]

    @property
    def saldo_calculado(self):
        """Saldo final esperado según la naturaleza de la cuenta."""
        if self.cuenta.naturaleza == "D":
            return self.saldo_inicial + self.debito - self.credito
        return self.saldo_inicial - self.debito + self.credito

    def __str__(self):
        return f"{self.periodo} {self.cuenta.codigo}"


class Movimiento(models.Model):
    periodo = models.ForeignKey("empresa.Periodo", on_delete=models.PROTECT, related_name="movimientos")
    archivo = models.ForeignKey("empresa.ArchivoCargado", on_delete=models.PROTECT, related_name="movimientos")
    fecha = models.DateField()
    comprobante = models.CharField(max_length=40, blank=True)
    documento = models.CharField(max_length=60, blank=True, db_index=True)
    cuenta = models.ForeignKey(Cuenta, on_delete=models.PROTECT, related_name="movimientos")
    nit = models.CharField(max_length=15, blank=True, db_index=True)
    tercero_nombre = models.CharField(max_length=250, blank=True)
    descripcion = models.CharField(max_length=300, blank=True)
    debito = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)
    credito = models.DecimalField(max_digits=20, decimal_places=2, default=CERO)

    class Meta:
        ordering = ["fecha", "id"]
        indexes = [models.Index(fields=["periodo", "cuenta"])]

    def __str__(self):
        return f"{self.fecha} {self.cuenta.codigo} D{self.debito} C{self.credito}"


def saldos_vigentes(periodo):
    return SaldoCuenta.objects.filter(periodo=periodo, archivo__vigente=True).select_related("cuenta")


def movimientos_vigentes(periodo):
    return Movimiento.objects.filter(periodo=periodo, archivo__vigente=True).select_related("cuenta")


def suma_prefijos(queryset, campo, prefijos):
    from django.db.models import Q, Sum

    if not prefijos:
        return CERO
    q = Q()
    for p in prefijos:
        q |= Q(cuenta__codigo__startswith=p)
    return queryset.filter(q).aggregate(t=Sum(campo))["t"] or CERO
