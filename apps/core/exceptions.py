"""
Centralized DRF exception handler.

Wraps ALL API errors into the standard response envelope:
    {
        "success": false,
        "details": "Human-readable message",
        "code": "ERROR_CODE",
        "status_code": 400
    }

Register in settings:
    REST_FRAMEWORK["EXCEPTION_HANDLER"] = "apps.core.exceptions.custom_exception_handler"
"""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def _extract_message(detail) -> str:
    """Extract a human-readable message from DRF's error detail."""
    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):
        # Take the first error message
        for item in detail:
            msg = _extract_message(item)
            if msg:
                return msg
        return "Validation error."

    if isinstance(detail, dict):
        for _key, value in detail.items():
            msg = _extract_message(value)
            if msg:
                return msg
        return "Validation error."

    return str(detail)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns a consistent JSON envelope.

    Handles:
        - DRF ValidationError → 400
        - DRF AuthenticationFailed / NotAuthenticated → 401
        - DRF PermissionDenied → 403
        - DRF NotFound / Django Http404 → 404
        - DRF Throttled → 429
        - All other DRF APIExceptions → their status code
        - Django ValidationError → 400
        - Django PermissionDenied → 403
        - Unhandled exceptions → 500
    """
    # Convert Django exceptions to DRF exceptions
    if isinstance(exc, Http404):
        exc = NotFound("Resource not found.")
    elif isinstance(exc, DjangoPermissionDenied):
        exc = PermissionDenied("Permission denied.")
    elif isinstance(exc, DjangoValidationError):
        exc = ValidationError(detail=exc.messages)

    # Let DRF handle it first (sets response, adds WWW-Authenticate headers, etc.)
    response = exception_handler(exc, context)

    if response is not None:
        return _build_error_response(exc, response.status_code)

    # Unhandled exception — log and return 500
    logger.exception(
        "Unhandled exception in %s",
        context.get("view", "unknown"),
    )
    return _build_error_response(
        exc=None,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ---------------------------------------------------------------------------
# Error code mapping
# ---------------------------------------------------------------------------
_EXCEPTION_CODE_MAP = {
    ValidationError: "VALIDATION_ERROR",
    AuthenticationFailed: "AUTHENTICATION_FAILED",
    NotAuthenticated: "NOT_AUTHENTICATED",
    PermissionDenied: "PERMISSION_DENIED",
    NotFound: "NOT_FOUND",
    Throttled: "THROTTLED",
}


def _build_error_response(exc, status_code: int) -> Response:
    """Build the standard error response envelope."""
    if exc is None:
        details = "An unexpected error occurred."
        code = "INTERNAL_ERROR"
    elif isinstance(exc, Throttled):
        wait = exc.wait
        details = f"Request was throttled. Try again in {int(wait)} seconds." if wait else "Too many requests."
        code = "THROTTLED"
    elif isinstance(exc, APIException):
        details = _extract_message(exc.detail)
        code = _EXCEPTION_CODE_MAP.get(type(exc), "ERROR")
    else:
        details = str(exc)
        code = "ERROR"

    return Response(
        {
            "success": False,
            "details": details,
            "code": code,
            "status_code": status_code,
        },
        status=status_code,
    )
