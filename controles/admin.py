from django.contrib import admin

from .models import Hallazgo, ReglaControl

admin.site.register([ReglaControl, Hallazgo])
