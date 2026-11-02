"""Service models."""

from django.db import models

from apps.common.models import BaseModel


class ServiceCategory(BaseModel):
    """Category grouping for services (e.g. Haircuts, Shaving)."""

    shop = models.ForeignKey("shop.Shop", on_delete=models.CASCADE, related_name="service_categories")
    name = models.CharField(max_length=255)
    icon = models.ImageField(upload_to="service_icons", null=True, blank=True)
    display_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.shop.name})"


class Service(BaseModel):
    """Services offered by the shop."""

    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name="services")
    shop = models.ForeignKey("shop.Shop", on_delete=models.CASCADE, related_name="services")
    barbers = models.ManyToManyField("user.User", related_name="services", blank=True)
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to="service_images", null=True, blank=True)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self) -> str:
        return f"{self.name} - {self.price} ({self.shop.name})"
