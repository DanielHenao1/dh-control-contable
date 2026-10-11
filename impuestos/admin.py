from django.contrib import admin

from .models import (
    AjusteICA,
    ConceptoRetencion,
    Declaracion,
    DiferenciaFiscal,
    Retencion,
    TarifaICA,
)

admin.site.register([AjusteICA, ConceptoRetencion, Retencion, Declaracion, DiferenciaFiscal, TarifaICA])
