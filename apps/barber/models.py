"""Barber staff models."""

from django.db import models

from apps.common.models import BaseModel


class Barber(BaseModel):
    """Barber staff profile."""

    ROLE_CHOICES = [
        ("staff", "Staff"),
        ("admin", "Admin"),
    ]

    user = models.OneToOneField(
        "user.User", on_delete=models.CASCADE, related_name="barber_profile", verbose_name="Barber User Account"
    )
    shop = models.ForeignKey("shop.Shop", on_delete=models.CASCADE, related_name="barbers")
    specialty = models.CharField(max_length=255, blank=True, default="")
    bio = models.TextField(blank=True, default="")
    experience_years = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="staff")
    calendar_access = models.BooleanField(default=True)
    client_details_access = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.username} ({self.specialty})"
