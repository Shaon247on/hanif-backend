"""
Abstract base model.

Every model in the project should inherit from BaseModel.
Provides: status, created_at, updated_at.
"""

from django.db import models

from apps.common.enums import Status


class BaseModel(models.Model):
    """
    Abstract base model providing standard fields.

    Fields:
        status: Active/Inactive/Draft/Deleted status tracking
        created_at: Auto-set on creation
        updated_at: Auto-set on every save
    """

    status = models.SmallIntegerField(
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    objects = models.Manager()

    class Meta:
        abstract = True
        ordering = ["-created_at"]
