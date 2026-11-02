"""
Throttle classes for rate limiting.

Configured in REST_FRAMEWORK settings. Override per-view as needed:

    class MyView(APIView):
        throttle_classes = [AuthLoginThrottle]
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AnonBurstThrottle(AnonRateThrottle):
    """30 requests/minute for anonymous users."""

    scope = "anon_burst"


class AnonSustainedThrottle(AnonRateThrottle):
    """500 requests/day for anonymous users."""

    scope = "anon_sustained"


class UserBurstThrottle(UserRateThrottle):
    """60 requests/minute for authenticated users."""

    scope = "user_burst"


class AuthLoginThrottle(AnonRateThrottle):
    """5 requests/minute — applied to login/register endpoints."""

    scope = "auth_login"
