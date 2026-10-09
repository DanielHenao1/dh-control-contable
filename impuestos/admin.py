from django.contrib import admin

from .models import ConceptoRetencion, Declaracion, DiferenciaFiscal, Retencion, TarifaICA

admin.site.register([ConceptoRetencion, Retencion, Declaracion, DiferenciaFiscal, TarifaICA])
