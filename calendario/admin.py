from django.contrib import admin

from .models import Festivo, Obligacion, ReglaVencimiento

admin.site.register([Festivo, ReglaVencimiento, Obligacion])
