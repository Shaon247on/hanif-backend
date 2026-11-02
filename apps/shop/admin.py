from django.contrib import admin
from apps.shop.models import Shop, BusinessHour, ShopGallery, ClientGroup, ClientMessage, BusinessOff

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass

@admin.register(BusinessHour)
class BusinessHourAdmin(admin.ModelAdmin):
    pass

@admin.register(BusinessOff)
class BusinessOffAdmin(admin.ModelAdmin):
    list_display = ("shop", "start_date", "end_date", "is_full_day", "reason", "is_active")
    list_filter = ("shop", "is_full_day", "is_active")
    search_fields = ("shop__name", "reason")

@admin.register(ShopGallery)
class ShopGalleryAdmin(admin.ModelAdmin):
    pass

@admin.register(ClientGroup)
class ClientGroupAdmin(admin.ModelAdmin):
    pass


# @admin.register(ShopBusinessHourOverride)
# class ShopBusinessHourOverrideAdmin(admin.ModelAdmin):
#     pass

# @admin.register(ShopBusinessHourOverrideBreak)
# class ShopBusinessHourOverrideBreakAdmin(admin.ModelAdmin):
#     pass

@admin.register(ClientMessage)
class ClientMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "shop", "group", "recipient", "sender", "created_at"]
