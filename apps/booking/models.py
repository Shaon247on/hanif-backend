"""Booking, appointment, refund, and review models."""

from django.db import models

from apps.common.models import BaseModel


class Booking(BaseModel):
    """Container for booking transactions and orders."""

    PAYMENT_METHOD_CHOICES = [
        ("card", "Card"),
        ("cash", "Cash"),
        ("mobile_banking", "Mobile Banking"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    BOOKING_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    SOURCE_APP = "app"
    SOURCE_WALK_IN = "walk_in"
    SOURCE_CHOICES = [
        (SOURCE_APP, "App"),
        (SOURCE_WALK_IN, "Walk-in"),
    ]

    booking_code = models.CharField(max_length=50, unique=True, help_text="e.g. BB-2026-X99")
    customer = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="bookings")
    shop = models.ForeignKey("shop.Shop", on_delete=models.CASCADE, related_name="bookings")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    status = models.CharField(max_length=20, choices=BOOKING_STATUS_CHOICES, default="pending")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=SOURCE_APP)
    google_event_id = models.CharField(max_length=255, blank=True, null=True, help_text="Google Calendar Event ID")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Booking {self.booking_code} ({self.status})"


class Appointment(BaseModel):
    """Specific scheduled service appointment inside a booking container."""

    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("no_show", "No Show"),
        ("cancelled", "Cancelled"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="appointments")
    service = models.ForeignKey("service.Service", on_delete=models.CASCADE, related_name="appointments")
    barber = models.ForeignKey("barber.Barber", on_delete=models.CASCADE, related_name="appointments")
    appointment_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["appointment_date", "start_time"]

    def __str__(self) -> str:
        return f"Appointment on {self.appointment_date} {self.start_time} with {self.barber}"


class Refund(BaseModel):
    """Refund requests for canceled or altered bookings."""

    STATUS_CHOICES = [
        ("requested", "Requested"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("processed", "Processed"),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="refunds")
    customer = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="refunds")
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="requested")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Refund for Booking {self.booking.booking_code} ({self.status})"


class ShopReview(BaseModel):
    """Verified customer reviews associated with a booking."""

    shop = models.ForeignKey("shop.Shop", on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey("user.User", on_delete=models.CASCADE, related_name="reviews")
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="review",
    )
    rating = models.PositiveSmallIntegerField(help_text="Rating from 1 to 5 stars")
    comment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Review for {self.shop.name} by {self.customer.username} ({self.rating}★)"
