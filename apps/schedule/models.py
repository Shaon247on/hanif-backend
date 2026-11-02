"""Schedule models for Barbers."""

from django.db import models

from apps.common.models import BaseModel


class BarberShift(BaseModel):
    """Recurring weekly shift. Date-specific changes belong in BarberShiftOverride."""

    DAY_CHOICES = [
        ("sunday", "Sunday"),
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
    ]

    barber = models.ForeignKey("barber.Barber", on_delete=models.CASCADE, related_name="shifts")
    day_of_week = models.CharField(
        max_length=10, choices=DAY_CHOICES, null=True, blank=True, help_text="Recurring weekly day"
    )
    shift_date = models.DateField(null=True, blank=True, help_text="Override date")
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["barber", "day_of_week"]),
            models.Index(fields=["barber", "shift_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["barber", "day_of_week"],
                condition=models.Q(shift_date__isnull=True),
                name="unique_recurring_barber_shift",
            ),
        ]
        ordering = ["shift_date", "day_of_week", "start_time"]

    def __str__(self) -> str:
        if self.shift_date:
            return f"{self.barber} Shift on {self.shift_date}: {self.start_time} - {self.end_time}"
        return f"{self.barber} Recurring {self.get_day_of_week_display()}: {self.start_time} - {self.end_time}"


class BarberBreak(BaseModel):
    """Recurring weekly daily break or single-day custom break."""

    DAY_CHOICES = [
        ("sunday", "Sunday"),
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
    ]

    barber = models.ForeignKey("barber.Barber", on_delete=models.CASCADE, related_name="breaks")
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES, null=True, blank=True)
    break_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    title = models.CharField(max_length=100, default="lunch")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["break_date", "day_of_week", "start_time"]

    def __str__(self) -> str:
        if self.break_date:
            return f"{self.barber} {self.title} on {self.break_date}: {self.start_time} - {self.end_time}"
        return f"{self.barber} {self.title} recurring {self.get_day_of_week_display()}: {self.start_time} - {self.end_time}"


class BarberTimeOff(BaseModel):
    """Barber leave requests (Full days or partial hours)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]

    barber = models.ForeignKey("barber.Barber", on_delete=models.CASCADE, related_name="time_offs")
    start_date = models.DateField()
    end_date = models.DateField(help_text="Same as start_date for single day leave")
    is_full_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True, help_text="Required if partial day off")
    end_time = models.TimeField(null=True, blank=True, help_text="Required if partial day off")
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        "user.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_time_offs"
    )

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "Barber Time Off"
        verbose_name_plural = "Barber Time Offs"

    def __str__(self) -> str:
        leave_range = (
            f"{self.start_date}" if self.start_date == self.end_date else f"{self.start_date} to {self.end_date}"
        )
        return f"{self.barber} - {leave_range} ({self.status})"


class BarberShiftOverride(BaseModel):
    """Specific date shift override for a barber (can change working hours or mark day as off)."""

    barber = models.ForeignKey("barber.Barber", on_delete=models.CASCADE, related_name="shift_overrides")
    date = models.DateField(help_text="Override date")
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    is_off = models.BooleanField(default=False, help_text="True if barber is completely off on this date")
    is_active = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        indexes = [
            models.Index(fields=["barber", "date"]),
        ]
        unique_together = ("barber", "date")
        ordering = ["date", "start_time"]
        verbose_name = "Barber Shift Override"
        verbose_name_plural = "Barber Shift Overrides"

    def __str__(self) -> str:
        if self.is_off:
            return f"{self.barber} OFF on {self.date}"
        return f"{self.barber} Shift on {self.date}: {self.start_time} - {self.end_time}"

