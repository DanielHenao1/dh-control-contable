from django.contrib import admin

from .models import Cuenta, Movimiento, SaldoCuenta

admin.site.register([Cuenta, SaldoCuenta, Movimiento])
