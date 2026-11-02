"""Notification models."""

from django.db import models

from apps.common.models import BaseModel


class Notification(BaseModel):
    """In-app notifications sent to users."""

    TYPE_CHOICES = [
        ("booking", "Booking"),
        ("promotion", "Promotion"),
        ("reminder", "Reminder"),
        ("system", "System"),
    ]

    user = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status_str = "Read" if self.is_read else "Unread"
        return f"[{status_str}] Notification for {self.user.username}: {self.title}"
