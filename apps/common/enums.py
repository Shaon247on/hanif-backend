"""
Global enums shared across all apps.

Usage:
    from apps.common.enums import Status

    status = models.SmallIntegerField(choices=Status.choices, default=Status.ACTIVE)
"""

from django.db import models


class Status(models.IntegerChoices):
    """Standard status field for all models."""

    DRAFT = 0, "Draft"
    ACTIVE = 1, "Active"
    INACTIVE = 2, "Inactive"
    DELETED = 3, "Deleted"
