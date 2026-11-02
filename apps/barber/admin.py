from django.contrib import admin
from apps.barber.models import Barber

@admin.register(Barber)
class BarberAdmin(admin.ModelAdmin):
    pass
