"""User-specific enums."""

from django.db import models


class UserRole(models.TextChoices):
    """User role choices."""

    SUPER_ADMIN = "SUPER_ADMIN", "Super Admin"
    ADMIN = "ADMIN", "Admin"
    USER = "USER", "User"
    BARBER = "BARBER", "Barber"
    MANAGER = "MANAGER", "Manager"