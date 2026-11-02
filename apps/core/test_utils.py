"""
Test utilities.

Provides:
    - BaseAPITestCase — base class for all API tests with helper methods
"""

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class BaseAPITestCase(TestCase):
    """
    Base test case for API tests.

    Provides:
        - Authenticated API client setup
        - Helper methods for common assertions
        - User creation utilities
    """

    client_class = APIClient

    def setUp(self):
        """Set up test client."""
        super().setUp()
        self.client = self.client_class()

    def create_user(
        self,
        email: str = "test@example.com",
        password: str = "TestPass123!",
        **kwargs,
    ):
        """Create and return a test user."""
        from apps.user.models import User

        defaults = {
            "username": email.split("@")[0],
            "email": email,
            "is_active": True,
            "status": 1,
        }
        defaults.update(kwargs)
        user = User(**defaults)
        user.set_password(password)
        user.save()
        return user

    def authenticate(self, user=None, email: str = None, password: str = "TestPass123!"):
        """Authenticate the test client with JWT."""
        if user is None:
            user = self.create_user(email=email or "auth@example.com", password=password)

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return user

    def assert_success(self, response, status_code: int = status.HTTP_200_OK):
        """Assert response is a success envelope."""
        self.assertEqual(response.status_code, status_code)
        data = response.json()
        self.assertTrue(data.get("success"), f"Expected success=True, got: {data}")
        return data

    def assert_error(self, response, status_code: int = status.HTTP_400_BAD_REQUEST):
        """Assert response is an error envelope."""
        self.assertEqual(response.status_code, status_code)
        data = response.json()
        self.assertFalse(data.get("success"), f"Expected success=False, got: {data}")
        return data
