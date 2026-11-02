from django.db import models

from apps.booking.models import Booking
from apps.common.models import BaseModel


class PaymentLog(BaseModel):
    """Logs all transactions: Webhook (Apple/Google Pay) and Manual payments."""

    METHOD_CHOICES = [
        ("apple_pay", "Apple Pay"),
        ("google_pay", "Google Pay"),
        ("cash", "Cash"),
        ("card", "Card"),
        ("mobile_banking", "Mobile Banking"),
        ("other", "Other"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_logs")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    transaction_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="ID from RevenueCat or Payment Gateway"
    )
    status = models.CharField(max_length=50, default="completed")
    raw_data = models.JSONField(blank=True, null=True, help_text="Webhook JSON payload")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        code = self.booking.booking_code if self.booking else "Unknown"
        return f"{self.method.upper()} - {self.amount} for Booking {code} ({self.status})"
