"""Shop models."""

from uuid import uuid4

from django.db import models
from django.template.defaultfilters import slugify

from apps.common.models import BaseModel


def get_logo_path(instance, filename):
    ext = filename.split(".")[-1]
    return f"shop_logos/{uuid4().hex[:12]}.{ext}"


def get_cover_path(instance, filename):
    ext = filename.split(".")[-1]
    return f"shop_cover_images/{uuid4().hex[:12]}.{ext}"


class Shop(BaseModel):
    """Core shop entity representing a salon."""

    owner = models.ForeignKey(
        "user.User", on_delete=models.CASCADE, related_name="shops", verbose_name="Shop Owner / Admin"
    )
    managers = models.ManyToManyField(
        "user.User", related_name="managed_shops", blank=True, verbose_name="Shop Managers"
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    logo = models.ImageField(upload_to=get_logo_path, blank=True, null=True)
    cover_image = models.ImageField(upload_to=get_cover_path, blank=True, null=True)
    location = models.CharField(max_length=1000)
    about_us = models.TextField(blank=True, default="")

    # contact
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, null=True)

    # social media
    facebook = models.CharField(max_length=255, blank=True, null=True)
    instagram = models.CharField(max_length=255, blank=True, null=True)
    tiktok = models.CharField(max_length=255, blank=True, null=True)
    twitter = models.CharField(max_length=255, blank=True, null=True)
    youtube = models.CharField(max_length=255, blank=True, null=True)
    google_review_link = models.URLField(max_length=500, blank=True, null=True)
    google_place_id = models.CharField(
        max_length=255, blank=True, null=True, help_text="Required to fetch Google Reviews"
    )

    payment_gateway_enabled = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # auto generate slug if not provided and unique
        if not self.slug:
            self.slug = f"{slugify(self.name)}-{uuid4().hex[:6]}"
        # check if slug already exists
        existing_shop = Shop.objects.filter(slug=self.slug).first()
        if existing_shop and existing_shop.pk != self.pk:
            self.slug = f"{slugify(self.name)}-{uuid4().hex[:6]}"
        super().save(*args, **kwargs)


class BusinessHour(BaseModel):
    """Business hours representing weekly schedules for a shop."""

    DAY_CHOICES = [
        ("sunday", "Sunday"),
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="business_hours")
    day_of_week = models.CharField(max_length=10, choices=DAY_CHOICES)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        unique_together = ("shop", "day_of_week")
        ordering = ["day_of_week"]

    def __str__(self) -> str:
        status_str = "Closed" if self.is_closed else f"{self.open_time} - {self.close_time}"
        return f"{self.shop.name} - {self.get_day_of_week_display()}: {status_str}"


class BusinessHourBreak(BaseModel):
    """One of multiple shop-level breaks inside a business day."""

    business_hour = models.ForeignKey(BusinessHour, on_delete=models.CASCADE, related_name="breaks")
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.business_hour} break: {self.start_time} - {self.end_time}"


class ShopBusinessHourOverride(BaseModel):
    """Date-specific shop hours that override the recurring business hours."""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="business_hour_overrides")
    date = models.DateField()
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    is_closed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["shop", "date"], name="unique_shop_business_date")]
        ordering = ["date"]


class ShopBusinessHourOverrideBreak(BaseModel):
    override = models.ForeignKey(ShopBusinessHourOverride, on_delete=models.CASCADE, related_name="breaks")
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["start_time"]


class BusinessOff(BaseModel):
    """Dates or time periods when the entire shop/business is closed (holidays, renovations, etc.)."""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="business_offs")
    start_date = models.DateField()
    end_date = models.DateField(help_text="End date of the business off period (same as start_date for single day off)")
    is_full_day = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True, help_text="Required if partial day off")
    end_time = models.TimeField(null=True, blank=True, help_text="Required if partial day off")
    reason = models.CharField(max_length=255, blank=True, default="", help_text="Reason e.g. Eid Holiday, Renovation")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "Business Off"
        verbose_name_plural = "Business Offs"

    def __str__(self):
        date_range = f"{self.start_date}" if self.start_date == self.end_date else f"{self.start_date} to {self.end_date}"
        return f"{self.shop.name} Off: {date_range} ({self.reason or 'Closed'})"


def get_gallery_path(instance, filename):
    ext = filename.split(".")[-1]
    return f"gallery_images/{uuid4().hex[:12]}.{ext}"


class ShopGallery(BaseModel):
    """Image gallery showcasing the shop."""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="gallery_images")
    image = models.ImageField(upload_to=get_gallery_path)
    display_order = models.IntegerField(default=0, null=True, blank=True)

    class Meta:
        ordering = ["display_order", "-created_at"]
        verbose_name_plural = "Shop Galleries"

    def __str__(self) -> str:
        return f"Gallery Image for {self.shop.name}"


class ClientGroup(BaseModel):
    """A group of clients managed by the shop admin."""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="client_groups")
    name = models.CharField(max_length=255)
    clients = models.ManyToManyField("user.User", related_name="client_groups", blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("shop", "name")

    def __str__(self) -> str:
        return f"{self.name} - {self.shop.name}"

class ClientMessage(BaseModel):
    """One-way message from a shop to a client group or to a single client."""

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="client_messages")
    sender = models.ForeignKey(
        "user.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_client_messages"
    )
    group = models.ForeignKey(ClientGroup, on_delete=models.CASCADE, null=True, blank=True, related_name="messages")
    recipient = models.ForeignKey(
        "user.User", on_delete=models.CASCADE, null=True, blank=True, related_name="received_client_messages"
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(group__isnull=False, recipient__isnull=True)
                | models.Q(group__isnull=True, recipient__isnull=False),
                name="client_message_has_one_target",
            ),
        ]

    def __str__(self) -> str:
        target = self.group.name if self.group else self.recipient.email
        return f"Message to {target} at {self.shop.name}"
