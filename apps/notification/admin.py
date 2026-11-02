from django.contrib import admin
from apps.notification.models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    pass
