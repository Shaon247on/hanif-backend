"""
Standard API response helpers.

Usage:
    from apps.core.responses import success_response, error_response

    return success_response("Created successfully.", data=serializer.data, status_code=201)
    return error_response("Invalid input.", code="VALIDATION_ERROR")
"""

from rest_framework import status as http_status
from rest_framework.response import Response


def success_response(
    details: str = "Success",
    code: str = "SUCCESS",
    status_code: int = http_status.HTTP_200_OK,
    data=None,
) -> Response:
    """Return a standardized success response."""
    payload = {
        "success": True,
        "details": details,
        "code": code,
        "status_code": status_code,
    }
    if data is not None:
        payload["data"] = data

    return Response(payload, status=status_code)


def error_response(
    details: str = "An error occurred.",
    code: str = "ERROR",
    status_code: int = http_status.HTTP_400_BAD_REQUEST,
    data=None,
) -> Response:
    """Return a standardized error response."""
    payload = {
        "success": False,
        "details": details,
        "code": code,
        "status_code": status_code,
    }
    if data is not None:
        payload["data"] = data

    return Response(payload, status=status_code)
