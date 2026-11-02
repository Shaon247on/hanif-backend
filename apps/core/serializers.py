"""
Base serializers and custom field mixins.

Provides:
    - BaseModelSerializer — auto read-only timestamps
    - ContextMixin — easy access to request/user/view from serializer context
    - ExtendedFileField — handles relative/absolute URL generation
    - Base64FileField / Base64ImageField — accept base64-encoded uploads
"""

import base64
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http.request import HttpRequest
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.settings import api_settings


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------
class ContextMixin:
    """Mixin for serializers to access request, user, and view from context."""

    def get_context_request(self) -> Request:
        return self.context.get("request")

    def get_context_view(self) -> GenericAPIView:
        return self.context.get("view")

    def get_context_user(self) -> AbstractUser:
        request = self.get_context_request()
        return request.user if request else None


# ---------------------------------------------------------------------------
# Base serializer
# ---------------------------------------------------------------------------
class BaseModelSerializer(ContextMixin, serializers.ModelSerializer):
    """
    ModelSerializer with auto read-only timestamps.

    All models inheriting from BaseModel get created_at/updated_at
    set as read-only automatically.
    """

    class Meta:
        abstract = True
        read_only_fields = ("created_at", "updated_at")


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------
class ExtendedFileField(serializers.FileField):
    """File field that generates full absolute URLs or relative paths."""

    def __init__(self, use_relative: bool = False, **kwargs):
        self.use_relative = use_relative
        super().__init__(**kwargs)

    def to_representation(self, value):
        if not value:
            return None

        if self.use_relative:
            return default_storage.url(value)

        if isinstance(value, str):
            path = default_storage.url(value)
        else:
            path = super().to_representation(value)
            if path is None:
                return None

        request: HttpRequest = self.context.get("request")
        if request is not None:
            use_url = getattr(self, "use_url", api_settings.UPLOADED_FILES_USE_URL)
            if use_url and isinstance(value, str):
                path = request.build_absolute_uri(default_storage.url(value))

        return path


class ExtendedImageField(ExtendedFileField, serializers.ImageField):
    """Image field with extended URL generation."""

    pass


class Base64FileField(ExtendedFileField):
    """Accept base64-encoded file data (e.g., data:application/pdf;base64,...)."""

    def to_internal_value(self, data):
        if isinstance(data, str) and "base64," in data:
            try:
                header, encoded = data.split(";base64,")
                file_extension = header.split("/")[-1]
                decoded = base64.b64decode(encoded)
                file_name = f"{uuid.uuid4()}.{file_extension}"
                data = ContentFile(decoded, name=file_name)
            except (ValueError, IndexError):
                self.fail("invalid")

        return super().to_internal_value(data)


class Base64ImageField(Base64FileField, serializers.ImageField):
    """Accept base64-encoded image data."""

    pass
