"""
Celery tasks for user-related async operations.

All email sending should go through these tasks so they don't block
the HTTP response.
"""

import logging

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from celery import shared_task
from config import env as env_module

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public task interface (called via .delay())
# ---------------------------------------------------------------------------
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, user_id: str, otp: str) -> None:
    """Send email verification OTP."""
    try:
        _send_verification_email(user_id, otp)
    except Exception as exc:
        logger.exception("Failed to send verification email for user %s", user_id)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_welcome_email_task(self, user_id: str) -> None:
    """Send welcome email after account activation."""
    try:
        _send_welcome_email(user_id)
    except Exception as exc:
        logger.exception("Failed to send welcome email for user %s", user_id)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_password_reset_otp_task(self, user_id: str, otp: str) -> None:
    """Send password reset OTP email."""
    try:
        _send_password_reset_otp(user_id, otp)
    except Exception as exc:
        logger.exception("Failed to send OTP email for user %s", user_id)
        raise self.retry(exc=exc) from exc


# ---------------------------------------------------------------------------
# Internal email sending functions (also called synchronously as fallback)
# ---------------------------------------------------------------------------
def _send_verification_email(user_id: str, otp: str) -> None:
    """Send the email verification email."""
    from apps.user.models import User

    user = User.objects.get(pk=user_id)
    display_name = user.get_full_name().strip() or user.username or "there"

    html_message = render_to_string(
        "emails/verification.html",
        {
            "user": user,
            "display_name": display_name,
            "otp": otp,
            "project_name": env_module.PROJECT_NAME,
            "year": timezone.now().year,
        },
    )

    send_mail(
        subject=f"Verify your {env_module.PROJECT_NAME} account",
        message=f"Hi {display_name}, verify your email using OTP: {otp}",
        from_email=env_module.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def _send_welcome_email(user_id: str) -> None:
    """Send the welcome email."""
    from apps.user.models import User

    user = User.objects.get(pk=user_id)
    display_name = user.get_full_name().strip() or user.username or "there"

    html_message = render_to_string(
        "emails/welcome.html",
        {
            "user": user,
            "display_name": display_name,
            "project_name": env_module.PROJECT_NAME,
            "year": timezone.now().year,
        },
    )

    send_mail(
        subject=f"Welcome to {env_module.PROJECT_NAME}",
        message=f"Hi {display_name}, welcome to {env_module.PROJECT_NAME}.",
        from_email=env_module.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def _send_password_reset_otp(user_id: str, otp: str) -> None:
    """Send the password reset OTP email."""
    from apps.user.models import User

    user = User.objects.get(pk=user_id)
    display_name = user.get_full_name().strip() or user.username or "there"

    html_message = render_to_string(
        "emails/password_reset_otp.html",
        {
            "user": user,
            "display_name": display_name,
            "otp": otp,
            "project_name": env_module.PROJECT_NAME,
            "year": timezone.now().year,
        },
    )

    send_mail(
        subject=f"{env_module.PROJECT_NAME} — Password Reset OTP",
        message=f"Your OTP for password reset is: {otp}",
        from_email=env_module.EMAIL_HOST_USER,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
