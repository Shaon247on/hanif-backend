from django.contrib import admin
from apps.booking.models import Booking, Appointment, Refund, ShopReview

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    pass

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    pass

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    pass

@admin.register(ShopReview)
class ShopReviewAdmin(admin.ModelAdmin):
    pass
