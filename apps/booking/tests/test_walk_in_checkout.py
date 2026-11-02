"""Walk-in orders, offline payments, tips and checkout."""

import datetime
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking
from apps.core.test_utils import BaseAPITestCase
from apps.notification.models import Notification
from apps.payment.models import PaymentLog
from apps.schedule.models import BarberShift
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessHour, Shop
from apps.user.enums import UserRole
from apps.user.models import User

FORBIDDEN = status.HTTP_403_FORBIDDEN
FAR_FUTURE = "2037-11-04"
MIDDAY = datetime.datetime(2037, 11, 4, 11, 0)


def at_midday():
    """Freezes "now" inside working hours so walk-ins start in an open slot."""
    return mock.patch(
        "django.utils.timezone.now",
        return_value=timezone.make_aware(MIDDAY),
    )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OrderTestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=self.admin, name="Shop", location="Dhaka", payment_gateway_enabled=True)
        self.other_shop = Shop.objects.create(owner=self.admin, name="Other", location="Dhaka")
        self.manager = self.create_user(email="manager@example.com", role=UserRole.MANAGER)
        self.shop.managers.add(self.manager)
        self.barber_user = self.create_user(email="barber@example.com", role=UserRole.BARBER)
        self.barber = Barber.objects.create(user=self.barber_user, shop=self.shop)
        self.other_barber = Barber.objects.create(
            user=self.create_user(email="barber2@example.com", role=UserRole.BARBER), shop=self.other_shop
        )
        self.customer = self.create_user(email="customer@example.com", full_name="Rahim", role=UserRole.USER)

        category = ServiceCategory.objects.create(shop=self.shop, name="Hair")
        self.cut = Service.objects.create(
            shop=self.shop, category=category, name="Cut", price="30.00", duration_minutes=30
        )
        self.shave = Service.objects.create(
            shop=self.shop, category=category, name="Shave", price="20.00", duration_minutes=30
        )
        for day, _ in BusinessHour.DAY_CHOICES:
            BusinessHour.objects.create(
                shop=self.shop, day_of_week=day, open_time=datetime.time(0, 30), close_time=datetime.time(23, 30)
            )
            BarberShift.objects.create(
                barber=self.barber, day_of_week=day, start_time=datetime.time(0, 30), end_time=datetime.time(23, 30)
            )

    def walk_in(self, **overrides):
        payload = {
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.cut.id],
            "payment_method": "cash",
            "customer_id": str(self.customer.id),
            **overrides,
        }
        with at_midday():
            return self.client.post("/api/v1/bookings/walk-in/", payload, format="json")

    def reservation(self, payment_method=None):
        self.authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/bookings/",
            {
                "customer_id": str(self.customer.id),
                "shop": self.shop.id,
                "barber": self.barber.id,
                "services": [self.cut.id],
                "appointment_date": FAR_FUTURE,
                "start_time": "10:00:00",
                **({"payment_method": payment_method} if payment_method else {}),
            },
            format="json",
        )
        return Booking.objects.get(pk=self.assert_success(response)["data"]["id"])

    def checkout(self, booking, **body):
        return self.client.post(f"/api/v1/bookings/{booking.id}/checkout/", body, format="json")


class WalkInOrderTests(OrderTestCase):
    def test_barber_manager_and_admin_can_create_orders(self):
        for index, user in enumerate((self.barber_user, self.manager, self.admin)):
            self.authenticate(user=user)
            hour = f"{13 + index}:00:00"
            self.assert_success(self.walk_in(start_time=hour))
        self.assertEqual(Booking.objects.filter(source=Booking.SOURCE_WALK_IN).count(), 3)

    def test_customer_cannot_create_a_walk_in_order(self):
        self.authenticate(user=self.customer)
        self.assert_error(self.walk_in(), FORBIDDEN)

    def test_staff_of_another_shop_cannot_create_an_order(self):
        self.authenticate(user=self.other_barber.user)
        self.assert_error(self.walk_in(), FORBIDDEN)

    def test_order_records_everything_and_takes_payment(self):
        self.authenticate(user=self.barber_user)
        data = self.assert_success(
            self.walk_in(services=[self.cut.id, self.shave.id], payment_method="card", tip_amount="5.00")
        )["data"]

        booking = Booking.objects.get(pk=data["id"])
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.shop, self.shop)
        self.assertEqual(booking.total_amount, Decimal("55.00"))
        self.assertEqual(booking.tip_amount, Decimal("5.00"))
        self.assertEqual(booking.payment_method, "card")
        self.assertEqual(booking.payment_status, "paid")
        self.assertEqual(booking.appointments.count(), 2)
        self.assertEqual(booking.appointments.first().barber, self.barber)

        log = PaymentLog.objects.get(booking=booking)
        self.assertEqual((log.amount, log.method), (Decimal("55.00"), "card"))

    def test_order_never_opens_the_payment_gateway(self):
        self.authenticate(user=self.manager)
        with mock.patch("apps.booking.views.requests.post") as stripe_call:
            self.assert_success(self.walk_in(payment_method="card"))
        stripe_call.assert_not_called()

    def test_order_can_stay_unpaid_until_after_the_service(self):
        self.authenticate(user=self.manager)
        data = self.assert_success(self.walk_in(is_paid=False))["data"]
        self.assertEqual(Booking.objects.get(pk=data["id"]).payment_status, "pending")
        self.assertFalse(PaymentLog.objects.exists())

    def test_only_cash_and_card_are_accepted(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.walk_in(payment_method="mobile_banking"))

    def test_existing_email_books_under_that_customer(self):
        self.authenticate(user=self.manager)
        response = self.walk_in(customer_id=None, customer={"email": "CUSTOMER@example.com", "full_name": "Other"})
        self.assert_success(response)

        self.assertEqual(User.objects.filter(email__iexact="customer@example.com").count(), 1)
        self.assertEqual(Booking.objects.get().customer, self.customer)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.full_name, "Rahim")

    def test_new_email_creates_a_customer_without_a_phone(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.walk_in(customer_id=None, customer={"email": "new@example.com", "full_name": "New"}))

        customer = User.objects.get(email="new@example.com")
        self.assertEqual(customer.role, UserRole.USER)
        self.assertEqual(Booking.objects.get().customer, customer)

    def test_a_staff_email_cannot_be_used_as_a_customer(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.walk_in(customer_id=None, customer={"email": self.admin.email}))
        self.assertFalse(Booking.objects.exists())

    def test_customer_details_are_required(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.walk_in(customer_id=None))

    def test_customer_is_told_the_order_id(self):
        self.authenticate(user=self.manager)
        code = self.assert_success(self.walk_in())["data"]["booking_code"]

        self.assertIn(code, Notification.objects.get(user=self.customer).message)
        self.assertEqual(mail.outbox[-1].to, [self.customer.email])
        self.assertIn(code, mail.outbox[-1].body)

    def test_new_customer_is_told_how_to_sign_in(self):
        self.authenticate(user=self.manager)
        self.walk_in(customer_id=None, customer={"email": "new@example.com"})
        self.assertIn("Forgot password", mail.outbox[-1].body)

    def test_customer_sees_the_order_in_their_bookings(self):
        self.authenticate(user=self.manager)
        code = self.assert_success(self.walk_in())["data"]["booking_code"]

        self.authenticate(user=self.customer)
        with at_midday():
            bookings = self.assert_success(self.client.get("/api/v1/booking/?type=upcoming"))["data"]
        self.assertIn(code, [booking["booking_code"] for booking in bookings])

    def test_busy_barber_cannot_be_double_booked(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.walk_in())
        self.assert_error(self.walk_in())
        self.assertEqual(Booking.objects.count(), 1)

    def test_failed_order_does_not_leave_a_new_customer_behind(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.walk_in())
        self.assert_error(self.walk_in(customer_id=None, customer={"email": "new@example.com"}))
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_barber_and_services_must_belong_to_the_shop(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.walk_in(barber=self.other_barber.id))

    def test_only_management_can_discount(self):
        self.authenticate(user=self.barber_user)
        self.assert_error(self.walk_in(discount="5.00"), FORBIDDEN)

        self.authenticate(user=self.manager)
        data = self.assert_success(self.walk_in(discount="5.00"))["data"]
        self.assertEqual(Booking.objects.get(pk=data["id"]).total_amount, Decimal("25.00"))


class CheckoutTests(OrderTestCase):
    def test_reservation_is_not_paid_until_checkout(self):
        booking = self.reservation("cash")
        self.assertEqual(booking.status, "confirmed")
        self.assertEqual(booking.payment_status, "pending")
        self.assertFalse(PaymentLog.objects.exists())

    def test_checkout_records_payment_tip_and_discount(self):
        booking = self.reservation()
        self.assert_success(self.checkout(booking, payment_method="cash", tip_amount="10.00", discount="5.00"))

        booking.refresh_from_db()
        self.assertEqual(booking.status, "completed")
        self.assertEqual(booking.payment_status, "paid")
        self.assertEqual(booking.payment_method, "cash")
        self.assertEqual(booking.tip_amount, Decimal("10.00"))
        self.assertEqual(booking.discount_amount, Decimal("5.00"))
        self.assertEqual(booking.total_amount, Decimal("35.00"))
        self.assertEqual(PaymentLog.objects.get(booking=booking).amount, Decimal("35.00"))

    def test_checkout_completes_appointments_and_frees_the_slot(self):
        booking = self.reservation()
        self.assert_success(self.checkout(booking, payment_method="cash"))
        self.assertEqual(Appointment.objects.get(booking=booking).status, "completed")

        response = self.client.get(
            f"/api/v1/bookings/available-slots/?barber_id={self.barber.id}&date={FAR_FUTURE}&services={self.cut.id}"
        )
        self.assertIn("10:00:00", self.assert_success(response)["data"])

    def test_added_services_are_billed(self):
        booking = self.reservation()
        self.assert_success(self.checkout(booking, payment_method="card", services=[self.cut.id, self.shave.id]))

        booking.refresh_from_db()
        self.assertEqual(booking.total_amount, Decimal("50.00"))
        self.assertEqual(booking.appointments.count(), 2)

    def test_paying_twice_is_rejected(self):
        booking = self.reservation()
        self.assert_success(self.checkout(booking, payment_method="cash"))
        self.assert_error(self.checkout(booking, payment_method="cash"))
        self.assertEqual(PaymentLog.objects.filter(booking=booking).count(), 1)

    def test_a_paid_order_completes_without_a_second_payment(self):
        self.authenticate(user=self.manager)
        data = self.assert_success(self.walk_in())["data"]
        booking = Booking.objects.get(pk=data["id"])

        self.assert_success(self.checkout(booking))

        booking.refresh_from_db()
        self.assertEqual(booking.status, "completed")
        self.assertEqual(PaymentLog.objects.filter(booking=booking).count(), 1)

    def test_payment_method_is_required_for_an_unpaid_order(self):
        booking = self.reservation("cash")
        self.assert_error(self.checkout(booking))
        booking.refresh_from_db()
        self.assertEqual(booking.status, "confirmed")

    def test_discount_cannot_exceed_the_services(self):
        booking = self.reservation()
        self.assert_error(self.checkout(booking, payment_method="cash", discount="31.00"))
        self.assertFalse(PaymentLog.objects.exists())

    def test_barber_can_check_out_but_not_discount(self):
        booking = self.reservation()
        self.authenticate(user=self.barber_user)
        self.assert_error(self.checkout(booking, payment_method="cash", discount="5.00"), FORBIDDEN)
        self.assert_success(self.checkout(booking, payment_method="cash", tip_amount="2.00"))

    def test_customer_and_other_shops_cannot_check_out(self):
        booking = self.reservation()
        for user in (self.customer, self.other_barber.user):
            self.authenticate(user=user)
            self.assert_error(self.checkout(booking, payment_method="cash"), FORBIDDEN)

    def test_payment_fields_cannot_be_changed_through_a_booking_edit(self):
        booking = self.reservation()
        body = {"payment_status": "paid", "tip_amount": "99.00"}
        self.assert_success(self.client.patch(f"/api/v1/bookings/{booking.id}/", body, format="json"))
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, "pending")
        self.assertEqual(booking.tip_amount, Decimal("0.00"))


class ReportingTests(OrderTestCase):
    def test_tips_and_payment_methods_are_reported_separately(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.walk_in(start_time="12:00:00", payment_method="cash", tip_amount="5.00"))
        self.assert_success(self.walk_in(start_time="14:00:00", payment_method="card", tip_amount="3.00"))

        data = self.assert_success(self.client.get(f"/api/v1/payments/manual/?shop={self.shop.id}"))["data"]
        self.assertEqual(data["total_revenue"], Decimal("68.00"))
        self.assertEqual(data["total_tips"], Decimal("8.00"))
        self.assertEqual(data["cash_total"], Decimal("35.00"))
        self.assertEqual(data["card_total"], Decimal("33.00"))

    def test_shop_report_keeps_tips_out_of_service_revenue(self):
        booking = self.reservation()
        Appointment.objects.filter(booking=booking).update(appointment_date=timezone.localdate())
        Booking.objects.filter(pk=booking.pk).update(status="pending")
        self.assert_success(self.checkout(booking, payment_method="cash", tip_amount="10.00"))

        data = self.assert_success(self.client.get(f"/api/v1/dashboard/reports/?shop={self.shop.id}"))["data"]
        self.assertEqual(data["total_revenue"], 30.0)
        self.assertEqual(data["total_tips"], 10.0)
        self.assertEqual(data["staff_breakdown"][0]["tips"], 10.0)
