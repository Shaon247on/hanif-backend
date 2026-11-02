"""Contact service layer — email notification logic."""

import logging

from django.conf import settings
from django.core.mail import send_mail

from config import env as env_module

logger = logging.getLogger(__name__)


def notify_admin_of_contact(contact) -> None:
    """
    Send notification email to admin when a contact form is submitted.

    Uses ADMIN_NOTIFICATION_EMAIL from env. Silently fails if not configured.
    """
    admin_email = env_module.ADMIN_NOTIFICATION_EMAIL
    if not admin_email:
        logger.warning("ADMIN_NOTIFICATION_EMAIL not set. Skipping notification.")
        return

    try:
        subject = f"New Contact Message from {contact.full_name}"
        message = (
            f"Name: {contact.full_name}\n"
            f"Email: {contact.email}\n"
            f"Phone: {contact.phone or 'Not provided'}\n\n"
            f"Message:\n{contact.message}"
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[admin_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send admin notification for contact %s", contact.pk)
