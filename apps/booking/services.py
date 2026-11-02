"""Booking service layer."""

import datetime
import logging
import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking
from apps.payment.models import PaymentLog
from apps.schedule.services import ScheduleService

logger = logging.getLogger(__name__)

SLOT_UNAVAILABLE_MESSAGE = (
    "The selected time slot is not available. It may conflict with shop hours, breaks, or existing appointments."
)
OFFLINE_PAYMENT_METHODS = [("cash", "Cash"), ("card", "Card")]


def lock_barber(barber):
    """Serialize bookings per barber so two requests cannot both take the same slot."""
    return Barber.objects.select_for_update().get(pk=barber.pk)


def generate_booking_code() -> str:
    return f"BB-{timezone.localdate().year}-{uuid.uuid4().hex[:6].upper()}"


def schedule_appointments(booking, services, barber, appointment_date, start_time, status="scheduled"):
    """Create one appointment per service, back to back, and return the services' total price."""
    current = datetime.datetime.combine(appointment_date, start_time)
    total = Decimal("0.00")
    for service in services:
        end = current + datetime.timedelta(minutes=service.duration_minutes)
        Appointment.objects.create(
            booking=booking,
            service=service,
            barber=barber,
            appointment_date=current.date(),
            start_time=current.time(),
            end_time=end.time(),
            price=service.price,
            status=status,
        )
        total += service.price
        current = end
    return total


def record_offline_payment(booking, method):
    """Cash or card taken at the shop. This never contacts a payment gateway."""
    booking.payment_method = method
    booking.payment_status = "paid"
    PaymentLog.objects.create(
        booking=booking,
        amount=booking.total_amount,
        method=method,
        status="completed",
        transaction_id=f"offline_{booking.booking_code}",
    )


@transaction.atomic
def create_walk_in_order(*, customer, shop, barber, services, start_time, payment_method, is_paid, tip_amount, discount):
    """Create today's order for a customer standing in the shop."""
    today = timezone.localdate()
    starts_now = start_time is None
    if starts_now:
        start_time = timezone.localtime().time().replace(second=0, microsecond=0)

    lock_barber(barber)
    total_duration = sum(service.duration_minutes for service in services)
    if not ScheduleService.is_slot_available(barber, today, start_time, total_duration, starts_now=starts_now):
        raise ValidationError("This barber is not available at that time. Please choose another time or barber.")

    booking = Booking.objects.create(
        booking_code=generate_booking_code(),
        customer=customer,
        shop=shop,
        total_amount=Decimal("0.00"),
        tip_amount=tip_amount,
        discount_amount=discount,
        payment_method=payment_method,
        payment_status="pending",
        status="confirmed",
        source=Booking.SOURCE_WALK_IN,
    )
    subtotal = schedule_appointments(booking, services, barber, today, start_time)
    booking.total_amount = subtotal + tip_amount - discount
    if is_paid:
        record_offline_payment(booking, payment_method)
    booking.save()
    return booking


@transaction.atomic
def checkout_booking(booking, *, payment_method=None, tip_amount=None, discount=None, services=None):
    """Finish an order: settle what is owed, complete its appointments and free the barber's slot."""
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.status in ("cancelled", "completed"):
        raise ValidationError(f"This booking is already {booking.status}.")

    is_unpaid = booking.payment_status != "paid"
    if is_unpaid:
        if not payment_method:
            raise ValidationError({"payment_method": "Choose cash or card."})

        if services is not None:
            first = booking.appointments.order_by("appointment_date", "start_time").first()
            booking.appointments.all().delete()
            schedule_appointments(booking, services, first.barber, first.appointment_date, first.start_time)

        subtotal = sum((item.price for item in booking.appointments.all()), Decimal("0.00"))
        booking.tip_amount = booking.tip_amount if tip_amount is None else tip_amount
        booking.discount_amount = booking.discount_amount if discount is None else discount
        if booking.discount_amount > subtotal:
            raise ValidationError({"discount": "Discount cannot exceed the services total."})
        booking.total_amount = subtotal + booking.tip_amount - booking.discount_amount
        record_offline_payment(booking, payment_method)

    booking.status = "completed"
    booking.save()
    booking.appointments.exclude(status="cancelled").update(status="completed")
    return booking
