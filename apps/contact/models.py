"""Contact & CMS models."""

from django.db import models

from apps.common.models import BaseModel


class Terms(BaseModel):
    """Terms and conditions — singleton-like (only 1 record)."""

    title = models.CharField(max_length=255, default="Terms and Conditions")
    content = models.TextField(default="")

    class Meta:
        verbose_name = "Terms"
        verbose_name_plural = "Terms"

    def __str__(self) -> str:
        return self.title


class Policy(BaseModel):
    """Privacy policy — singleton-like (only 1 record)."""

    title = models.CharField(max_length=255, default="Privacy Policy")
    content = models.TextField(default="")

    class Meta:
        verbose_name = "Policy"
        verbose_name_plural = "Policies"

    def __str__(self) -> str:
        return self.title


class FAQ(BaseModel):
    """Frequently asked questions."""

    question = models.CharField(max_length=500)
    answer = models.TextField()
    order = models.IntegerField(default=0, help_text="Lower numbers appear first.")

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ["order", "-created_at"]

    def __str__(self) -> str:
        return self.question


class ContactMessage(BaseModel):
    """Contact form submissions."""

    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default="")
    message = models.TextField()
    is_replied = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Message from {self.full_name}"
