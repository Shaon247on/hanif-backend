"""Contact admin configuration."""

from django.contrib import admin

from apps.contact.models import FAQ, ContactMessage, Policy, Terms


@admin.register(Terms)
class TermsAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "status", "created_at")
    list_filter = ("status",)
    list_editable = ("order", "status")
    search_fields = ("question", "answer")


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("full_name", "email", "is_replied", "created_at")
    list_filter = ("is_replied",)
    search_fields = ("full_name", "email", "message")
    readonly_fields = ("full_name", "email", "phone", "message", "created_at")
