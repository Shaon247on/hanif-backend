from datetime import timedelta

from django.utils import timezone

from apps.booking.models import Appointment
from celery import shared_task

from .utils import send_push_and_email


@shared_task
def send_appointment_reminders():
    """
    Runs every minute. Finds appointments that are starting in exactly 5 minutes.
    Sends push notification and email to the user.
    """
    now = timezone.now()
    target_time_start = now + timedelta(minutes=5)
    target_time_end = now + timedelta(minutes=6)

    # We need to find appointments where appointment_date and start_time
    # fall exactly within the next 5-6 minutes window.

    # Since appointments are grouped by date and time in local/DB time,
    # let's assume the server is running in the correct timezone.
    target_date = target_time_start.date()
    start_t = target_time_start.time()
    end_t = target_time_end.time()

    upcoming_appointments = Appointment.objects.filter(
        appointment_date=target_date, start_time__gte=start_t, start_time__lt=end_t, status="scheduled"
    ).select_related("booking", "booking__customer", "booking__shop")

    for appt in upcoming_appointments:
        user = appt.booking.customer
        shop_name = appt.booking.shop.name if appt.booking.shop else "our shop"

        # Send Notification and Email
        send_push_and_email(
            user=user,
            title="Upcoming Appointment Reminder",
            message=f"Reminder: Your appointment for {appt.service.name} at {shop_name} starts in 5 minutes!",
            notif_type="reminder",
            send_email=True,
        )
