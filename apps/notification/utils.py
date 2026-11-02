from django.conf import settings
from django.core.mail import send_mail

from apps.user.models import User

from .models import Notification


def send_push_and_email(user: User, title: str, message: str, notif_type: str = "system", send_email: bool = True):
    """Utility to create a push notification and send an email."""
    user_settings = getattr(user, "settings", None)
    push_enabled = user_settings.push_notifications_enabled if user_settings else True
    email_enabled = user_settings.email_notifications_enabled if user_settings else True

    # Create Push Notification
    if push_enabled:
        Notification.objects.create(user=user, title=title, message=message, type=notif_type)

    # Send Email
    if send_email and email_enabled and user.email:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL
                if hasattr(settings, "DEFAULT_FROM_EMAIL")
                else "noreply@barberbay.com",
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send email to {user.email}: {e}")
