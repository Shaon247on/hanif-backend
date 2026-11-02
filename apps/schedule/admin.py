from django.contrib import admin
from apps.schedule.models import BarberBreak, BarberShift, BarberShiftOverride, BarberTimeOff

@admin.register(BarberShift)
class BarberShiftAdmin(admin.ModelAdmin):
    list_display = ["id", "barber", "day_of_week", "shift_date", "start_time", "end_time", "is_active"]
    list_filter = ["day_of_week", "is_active"]

@admin.register(BarberShiftOverride)
class BarberShiftOverrideAdmin(admin.ModelAdmin):
    list_display = ["id", "barber", "date", "start_time", "end_time", "is_off", "is_active"]
    list_filter = ["is_off", "is_active", "date"]

@admin.register(BarberBreak)
class BarberBreakAdmin(admin.ModelAdmin):
    list_display = ["id", "barber", "day_of_week", "break_date", "start_time", "end_time", "title", "is_active"]

@admin.register(BarberTimeOff)
class BarberTimeOffAdmin(admin.ModelAdmin):
    list_display = ["id", "barber", "start_date", "end_date", "is_full_day", "status"]
    list_filter = ["status", "is_full_day"]

