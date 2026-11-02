"""
Custom authentication backends.

Allows users to log in using email instead of username.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend

User = get_user_model()


class EmailAuthenticationBackend(BaseBackend):
    """Authenticate users by email + password."""

    def authenticate(self, request, email=None, password=None, **kwargs):
        if email is None or password is None:
            return None

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Run the default password hasher to mitigate timing attacks
            User().set_password(password)
            return None

        if user.check_password(password) and self._user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    @staticmethod
    def _user_can_authenticate(user) -> bool:
        """Reject users with is_active=False."""
        return getattr(user, "is_active", False)
