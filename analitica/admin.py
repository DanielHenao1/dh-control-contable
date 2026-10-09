from django.contrib import admin

from .models import Estimacion, Simulacion

admin.site.register([Estimacion, Simulacion])
