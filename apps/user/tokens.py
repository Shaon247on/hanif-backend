"""Email verification token generator."""

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Generate time-limited tokens for email verification."""

    def _make_hash_value(self, user, timestamp):
        login_timestamp = ""
        if user.last_login is not None:
            login_timestamp = user.last_login.replace(microsecond=0, tzinfo=None)

        return f"{user.pk}{user.password}{login_timestamp}{timestamp}{user.is_active}{user.email}"

    def check_token(self, user, token):
        """Check token validity with configurable timeout."""
        if not (user and token):
            return False

        try:
            ts_b36, _hash = token.split("-")
            timestamp = base36_to_int(ts_b36)
        except (ValueError, TypeError):
            return False

        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, timestamp, secret),
                token,
            ):
                break
        else:
            return False

        timeout = getattr(settings, "EMAIL_VERIFICATION_TIMEOUT", 86400)
        return (self._num_seconds(self._now()) - timestamp) <= timeout


email_verification_token_generator = EmailVerificationTokenGenerator()
