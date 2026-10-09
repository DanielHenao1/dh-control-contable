from django.contrib import admin

from .models import Contratista, Entrega, InformeContratista, Observacion

admin.site.register([Contratista, Entrega, InformeContratista, Observacion])
