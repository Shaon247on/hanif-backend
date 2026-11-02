"""User models."""

import re
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from apps.common.enums import Status
from apps.common.models import BaseModel
from apps.user.enums import UserRole
from apps.user.managers import UserManager


class User(AbstractUser):
    """
    Custom user model with UUID primary key and email-based auth.

    Extends Django's AbstractUser. Uses email as the primary identifier
    while keeping username for display/URL purposes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    status = models.SmallIntegerField(choices=Status.choices, default=Status.ACTIVE)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.USER,
        db_index=True,
    )
    full_name = models.CharField(max_length=255, blank=True, default="")
    image = models.ImageField(upload_to="profile/", null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True, default="")
    address = models.CharField(max_length=500, blank=True, default="")
    last_active_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    active_shop = models.ForeignKey(
        "shop.Shop", on_delete=models.SET_NULL, null=True, blank=True, related_name="active_users"
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return self.email

    def update_last_active(self) -> None:
        """Update last_active_at without triggering full save."""
        self.last_active_at = timezone.now()
        User.objects.filter(pk=self.pk).update(last_active_at=self.last_active_at)

    def set_unique_username(self) -> None:
        """Generate a unique username from email."""
        email = self.email or ""
        base_name = email.split("@")[0] if "@" in email else email
        base_name = re.sub(r"\d+$", "", base_name) or "user"

        existing = set(
            User.objects.filter(username__regex=rf"^{re.escape(base_name)}\d*$").values_list("username", flat=True)
        )

        if base_name not in existing:
            self.username = str(base_name)  # type: ignore
            return

        suffix = 1
        while f"{base_name}{suffix}" in existing:
            suffix += 1
        self.username = f"{base_name}{suffix}"  # type: ignore


class OTP(BaseModel):
    """OTP for email verification and password reset flows."""

    class OTPType(models.TextChoices):
        REGISTER = "register", "Registration Verification"
        PASSWORD_RESET = "password_reset", "Password Reset"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    otp = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    type = models.CharField(max_length=20, choices=OTPType.choices)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_type_display()} OTP for {self.user.email}"

    def is_expired(self) -> bool:
        """Check if OTP has expired (5 minutes)."""
        return timezone.now() > self.created_at + timedelta(minutes=5)  # type: ignore


class LocationService(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="location_service")
    location_name = models.CharField(max_length=200, null=True, blank=True)
    location_link = models.URLField(null=True, blank=True)


class Setting(BaseModel):
    """Settings table for user-specific or shop-specific feature configurations."""

    user = models.OneToOneField(
        "user.User", on_delete=models.CASCADE, related_name="settings", verbose_name="User Settings"
    )

    push_notifications_enabled = models.BooleanField(default=True)
    email_notifications_enabled = models.BooleanField(default=True)
    sms_notifications_enabled = models.BooleanField(default=False)
    dark_mode_enabled = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Settings for {self.user.email}"
