"""
User views — thin controllers that delegate to services.

No business logic here. Views handle:
    1. Parse request
    2. Validate via serializer
    3. Call service
    4. Return response
"""

from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView  # noqa: F401

from apps.core.responses import success_response
from apps.core.throttles import AuthLoginThrottle
from apps.user import serializers as user_serializers
from apps.user import services as user_services


# ---------------------------------------------------------------------------
# Registration & verification
# ---------------------------------------------------------------------------
class RegisterAPIView(generics.GenericAPIView):
    """Register a new user account."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]
    serializer_class = user_serializers.RegisterSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.register_user(serializer.validated_data, request=request)
        return success_response(
            details="Registration successful. Verification email sent.",
            code="REGISTER_SUCCESS",
            status_code=status.HTTP_201_CREATED,
        )


class EmailVerificationAPIView(generics.GenericAPIView):
    """Verify user email via 6-digit OTP."""

    permission_classes = [AllowAny]
    serializer_class = user_serializers.EmailVerificationSerializer

    def _verify(self, data):
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        tokens = user_services.verify_email(
            email=serializer.validated_data["email"],
            otp=serializer.validated_data["otp"],
        )
        return success_response(
            details="Email verified successfully.",
            code="EMAIL_VERIFIED",
            data=tokens,
        )

    def get(self, request):
        return self._verify(
            {
                "email": request.query_params.get("email"),
                "otp": request.query_params.get("otp"),
            }
        )

    def post(self, request):
        return self._verify(request.data)


class ResendOTPAPIView(generics.GenericAPIView):
    """Resend OTP for email verification or password reset."""

    permission_classes = [AllowAny]
    serializer_class = user_serializers.ResendOTPSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.resend_otp(
            email=serializer.validated_data["email"],
            otp_type=serializer.validated_data["type"],
        )
        return success_response(
            details="OTP resent successfully.",
            code="OTP_RESENT",
        )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class EmailLoginAPIView(TokenObtainPairView):
    """Login via email and password. Returns JWT tokens + user profile + shops."""

    throttle_classes = [AuthLoginThrottle]
    serializer_class = user_serializers.EmailLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return success_response(
            details="Login successful.",
            code="LOGIN_SUCCESS",
            data={
                "refresh": serializer.validated_data["refresh"],
                "access": serializer.validated_data["access"],
                "user": serializer.validated_data["user"],
                "shops": serializer.validated_data.get("shops", []),
                "active_shop": serializer.validated_data["user"].get("active_shop"),
            },
        )


class TokenRefreshAPIView(TokenRefreshView):
    """Custom token refresh view that returns a standardized success response."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        return success_response(
            details="Token refreshed successfully.",
            code="TOKEN_REFRESH_SUCCESS",
            data=response.data,
        )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileAPIView(generics.RetrieveAPIView):
    """Get the authenticated user's profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = user_serializers.UserProfileSerializer

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(
            details="Profile retrieved.",
            code="PROFILE_SUCCESS",
            data=serializer.data,
        )


class ProfileUpdateAPIView(generics.UpdateAPIView):
    """Update the authenticated user's profile."""

    permission_classes = [IsAuthenticated]
    serializer_class = user_serializers.ProfileUpdateSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["patch"]

    def get_object(self):
        return self.request.user

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            details="Profile updated.",
            code="PROFILE_UPDATED",
            data=serializer.data,
        )


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------
class PasswordChangeAPIView(generics.GenericAPIView):
    """Change password using current password."""

    permission_classes = [IsAuthenticated]
    serializer_class = user_serializers.PasswordChangeSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.change_password(request.user, serializer.validated_data["new_password"])
        return success_response(details="Password changed.", code="PASSWORD_CHANGED")


class PasswordResetRequestAPIView(generics.GenericAPIView):
    """Request a password reset OTP via email."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]
    serializer_class = user_serializers.PasswordResetRequestSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.request_password_reset(serializer.validated_data["email"])
        return success_response(
            details="If an account exists, an OTP has been sent.",
            code="OTP_SENT",
        )


class PasswordOTPVerifyAPIView(generics.GenericAPIView):
    """Verify a password reset OTP."""

    permission_classes = [AllowAny]
    serializer_class = user_serializers.PasswordOTPVerifySerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.verify_otp(
            email=serializer.validated_data["email"],
            otp=serializer.validated_data["otp"],
        )
        return success_response(details="OTP is valid.", code="OTP_VALID")


class PasswordResetConfirmAPIView(generics.GenericAPIView):
    """Reset password using OTP."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]
    serializer_class = user_serializers.PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_services.reset_password(
            email=serializer.validated_data["email"],
            otp=serializer.validated_data["otp"],
            new_password=serializer.validated_data["new_password"],
        )
        return success_response(details="Password reset successfully.", code="PASSWORD_RESET")


class LocationAPIView(generics.GenericAPIView):
    """Get, create, or update the current user's location service."""

    permission_classes = [IsAuthenticated]
    serializer_class = user_serializers.LocationServiceSerializer

    def get(self, request):
        location_service = user_services.get_location_service(request.user)
        if not location_service:
            return success_response(
                details="Location service not found.",
                code="LOCATION_SERVICE_NOT_FOUND",
                data=None,
            )
        serializer = self.get_serializer(location_service)
        return success_response(
            details="Location service retrieved.",
            code="LOCATION_SERVICE_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location_service = user_services.create_or_update_location_service(request.user, serializer.validated_data)
        return success_response(
            details="Location service saved successfully.",
            code="LOCATION_SERVICE_SAVED",
            data=self.get_serializer(location_service).data,
        )

    def put(self, request):
        return self.post(request)

class UserSettingAPIView(generics.GenericAPIView):
    """GET/PUT: Manage user notification and theme settings."""
    permission_classes = [IsAuthenticated]
    serializer_class = user_serializers.SettingSerializer

    def get_object(self):
        from apps.user.models import Setting
        setting, _ = Setting.objects.get_or_create(user=self.request.user)
        return setting

    def get(self, request, *args, **kwargs):
        setting = self.get_object()
        serializer = self.get_serializer(setting)
        return success_response(
            details="User settings retrieved successfully.",
            code="USER_SETTINGS_RETRIEVED",
            data=serializer.data
        )

    def put(self, request, *args, **kwargs):
        setting = self.get_object()
        serializer = self.get_serializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            details="User settings updated successfully.",
            code="USER_SETTINGS_UPDATED",
            data=serializer.data
        )
