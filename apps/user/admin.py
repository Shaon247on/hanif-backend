"""User admin configuration."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.user.models import OTP, User, LocationService, Setting


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom user admin with role and status fields."""

    list_display = ("email", "username", "role", "status", "is_active", "date_joined")
    list_filter = ("role", "status", "is_active", "is_staff")
    search_fields = ("email", "username", "first_name", "last_name")
    ordering = ("-date_joined",)

    fieldsets = BaseUserAdmin.fieldsets + (
        ("Extended", {"fields": ("role", "status", "image", "phone", "address", "last_active_at")}),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ("user", "otp", "type", "is_used", "created_at")
    list_filter = ("type", "is_used")
    search_fields = ("user__email",)
    readonly_fields = ("otp", "created_at")


@admin.register(LocationService)
class LocationServiceAdmin(admin.ModelAdmin):
    pass


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    pass
