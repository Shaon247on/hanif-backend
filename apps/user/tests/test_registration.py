"""Tests for user registration."""

from django.test import override_settings
from rest_framework import status

from apps.core.test_utils import BaseAPITestCase


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class RegistrationTests(BaseAPITestCase):
    """Test user registration flow."""

    url = "/api/v1/auth/register/"

    def test_register_success(self):
        """Successful registration returns 201."""
        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
        )
        self.assert_success(response, status.HTTP_201_CREATED)

    def test_register_duplicate_email(self):
        """Duplicate email returns 400."""
        self.create_user(email="existing@example.com")
        response = self.client.post(
            self.url,
            {
                "email": "existing@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
        )
        self.assert_error(response, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        """Mismatched passwords return 400."""
        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "StrongPass123!",
                "confirm_password": "DifferentPass456!",
            },
        )
        self.assert_error(response, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        """Weak password returns 400."""
        response = self.client.post(
            self.url,
            {
                "email": "new@example.com",
                "password": "123",
                "confirm_password": "123",
            },
        )
        self.assert_error(response, status.HTTP_400_BAD_REQUEST)

    def test_verify_email_success(self):
        """Successful OTP verification activates the user and returns tokens."""
        # 1. Register
        register_response = self.client.post(
            self.url,
            {
                "email": "verify_me@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
        )
        self.assert_success(register_response, status.HTTP_201_CREATED)

        # Retrieve the generated OTP from database
        from apps.user.models import OTP, User

        user = User.objects.get(email="verify_me@example.com")
        self.assertFalse(user.is_active)

        otp_obj = OTP.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(otp_obj)

        # 2. Verify Email
        verify_response = self.client.post(
            "/api/v1/auth/verify-email/",
            {
                "email": "verify_me@example.com",
                "otp": otp_obj.otp,
            },
        )
        data = self.assert_success(verify_response, status.HTTP_200_OK)
        self.assertIn("access", data["data"])
        self.assertIn("refresh", data["data"])

        # Check user is now active
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        # Check OTP is now used
        otp_obj.refresh_from_db()
        self.assertTrue(otp_obj.is_used)

    def test_verify_email_invalid_otp(self):
        """Incorrect OTP returns 400."""
        # Register
        self.client.post(
            self.url,
            {
                "email": "verify_fail@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
        )
        # Verify with wrong OTP
        verify_response = self.client.post(
            "/api/v1/auth/verify-email/",
            {
                "email": "verify_fail@example.com",
                "otp": "000000",
            },
        )
        self.assert_error(verify_response, status.HTTP_400_BAD_REQUEST)

    def test_resend_verification_otp_success(self):
        """Resending verification OTP invalidates the old one and generates a new one."""
        # 1. Register
        self.client.post(
            self.url,
            {
                "email": "resend_me@example.com",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
        )

        from apps.user.models import OTP, User

        user = User.objects.get(email="resend_me@example.com")
        old_otp_obj = OTP.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(old_otp_obj)

        # 2. Resend OTP
        resend_response = self.client.post(
            "/api/v1/auth/resend-otp/",
            {
                "email": "resend_me@example.com",
                "type": "register",
            },
        )
        self.assert_success(resend_response, status.HTTP_200_OK)

        # Verify old OTP is invalidated
        old_otp_obj.refresh_from_db()
        self.assertTrue(old_otp_obj.is_used)

        # Verify new OTP is generated
        new_otp_obj = OTP.objects.filter(user=user, is_used=False).first()
        self.assertIsNotNone(new_otp_obj)
        self.assertNotEqual(old_otp_obj.otp, new_otp_obj.otp)
