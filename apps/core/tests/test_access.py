"""Role and shop isolation rules, checked end to end through the API."""

import datetime
import hashlib
import hmac
import json
import time
from unittest import mock

from rest_framework import status

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking
from apps.core.test_utils import BaseAPITestCase
from apps.payment.models import PaymentLog
from apps.schedule.models import BarberShift, BarberTimeOff
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessHour, Shop
from apps.user.enums import UserRole
from apps.user.models import User

FORBIDDEN = status.HTTP_403_FORBIDDEN


class ShopAccessTestCase(BaseAPITestCase):
    """Two shops, each with a manager and a barber, plus an admin and two customers."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin@example.com", role=UserRole.ADMIN)
        self.other_admin = self.create_user(email="owner@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=self.other_admin, name="Shop A", location="A")
        self.other_shop = Shop.objects.create(owner=self.other_admin, name="Shop B", location="B")

        self.manager = self.create_user(email="manager@example.com", role=UserRole.MANAGER)
        self.shop.managers.add(self.manager)
        self.other_manager = self.create_user(email="manager2@example.com", role=UserRole.MANAGER)
        self.other_shop.managers.add(self.other_manager)

        self.barber_user = self.create_user(email="barber@example.com", role=UserRole.BARBER)
        self.barber = Barber.objects.create(user=self.barber_user, shop=self.shop)
        self.other_barber_user = self.create_user(email="barber2@example.com", role=UserRole.BARBER)
        self.other_barber = Barber.objects.create(user=self.other_barber_user, shop=self.other_shop)

        self.customer = self.create_user(email="customer@example.com", role=UserRole.USER)
        self.other_customer = self.create_user(email="customer2@example.com", role=UserRole.USER)

        self.category = ServiceCategory.objects.create(shop=self.shop, name="Hair")
        self.service = Service.objects.create(
            shop=self.shop, category=self.category, name="Cut", price="30.00", duration_minutes=30
        )
        self.service.barbers.add(self.barber_user)
        self.other_category = ServiceCategory.objects.create(shop=self.other_shop, name="Hair")
        self.other_service = Service.objects.create(
            shop=self.other_shop, category=self.other_category, name="Cut", price="30.00", duration_minutes=30
        )

        for day, _ in BusinessHour.DAY_CHOICES:
            BusinessHour.objects.create(
                shop=self.shop, day_of_week=day, open_time=datetime.time(8, 0), close_time=datetime.time(20, 0)
            )
            BarberShift.objects.create(
                barber=self.barber, day_of_week=day, start_time=datetime.time(9, 0), end_time=datetime.time(19, 0)
            )

        self.booking = self.make_booking(self.customer, "BB-TEST-1")

    def make_booking(self, customer, code):
        booking = Booking.objects.create(booking_code=code, customer=customer, shop=self.shop, total_amount="30.00")
        Appointment.objects.create(
            booking=booking,
            service=self.service,
            barber=self.barber,
            appointment_date=datetime.date(2030, 1, 7),
            start_time=datetime.time(10, 0),
            end_time=datetime.time(10, 30),
            price="30.00",
        )
        return booking

    def booking_payload(self, **overrides):
        return {
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2030-01-08",
            "start_time": "11:00:00",
            **overrides,
        }


class ShopAndManagerRulesTests(ShopAccessTestCase):
    def test_every_admin_reaches_every_shop(self):
        self.authenticate(user=self.admin)
        response = self.client.get("/api/v1/auth/profile/")
        data = self.assert_success(response)["data"]
        self.assertEqual({shop["id"] for shop in data["shops"]}, {self.shop.id, self.other_shop.id})

        response = self.client.put(f"/api/v1/shops/{self.other_shop.id}/", {"about_us": "Updated"}, format="json")
        self.assert_success(response)

    def test_manager_edits_only_their_own_shop(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.client.put(f"/api/v1/shops/{self.shop.id}/", {"about_us": "Mine"}, format="json"))
        self.assert_error(
            self.client.put(f"/api/v1/shops/{self.other_shop.id}/", {"about_us": "No"}, format="json"), FORBIDDEN
        )

    def test_only_admins_create_or_delete_shops(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.client.post("/api/v1/shops/", {"name": "New", "location": "X"}), FORBIDDEN)
        self.assert_error(self.client.delete(f"/api/v1/shops/{self.shop.id}/"), FORBIDDEN)

    def test_customer_cannot_change_a_shop(self):
        self.authenticate(user=self.customer)
        self.assert_error(self.client.put(f"/api/v1/shops/{self.shop.id}/", {"about_us": "x"}, format="json"), FORBIDDEN)
        self.assert_error(self.client.delete(f"/api/v1/shops/{self.shop.id}/"), FORBIDDEN)
        self.assertTrue(Shop.objects.filter(pk=self.shop.id).exists())

    def test_only_admins_create_managers(self):
        payload = {"email": "new@example.com", "password": "Secret123!", "shop_ids": [self.shop.id]}
        self.authenticate(user=self.manager)
        self.assert_error(self.client.post("/api/v1/shops/managers/", payload, format="json"), FORBIDDEN)

        self.authenticate(user=self.admin)
        self.assert_success(self.client.post("/api/v1/shops/managers/", payload, format="json"))
        self.assertEqual(User.objects.get(email="new@example.com").role, UserRole.MANAGER)

    def test_manager_is_limited_to_one_shop(self):
        self.authenticate(user=self.admin)
        two_shops = {
            "email": "new@example.com",
            "password": "Secret123!",
            "shop_ids": [self.shop.id, self.other_shop.id],
        }
        self.assert_error(self.client.post("/api/v1/shops/managers/", two_shops, format="json"))

        already_assigned = {"email": self.manager.email, "password": "x", "shop_ids": [self.other_shop.id]}
        self.assert_error(self.client.post("/api/v1/shops/managers/", already_assigned, format="json"))

        response = self.client.patch(
            f"/api/v1/shops/managers/{self.manager.id}/", {"shop_ids": [self.shop.id, self.other_shop.id]}, format="json"
        )
        self.assert_error(response)
        self.assertEqual(self.manager.managed_shops.count(), 1)

    def test_admin_can_reassign_a_manager_to_another_shop(self):
        self.authenticate(user=self.admin)
        response = self.client.patch(
            f"/api/v1/shops/managers/{self.manager.id}/", {"shop_ids": [self.other_shop.id]}, format="json"
        )
        self.assert_success(response)
        self.assertEqual(list(self.manager.managed_shops.all()), [self.other_shop])

    def test_staff_endpoint_cannot_create_a_manager(self):
        self.authenticate(user=self.manager)
        response = self.client.post(
            f"/api/v1/dashboard/shops/{self.shop.id}/staff/",
            {"email": "sneaky@example.com", "name": "Sneaky", "role": "manager"},
            format="json",
        )
        self.assert_success(response)
        self.assertEqual(User.objects.get(email="sneaky@example.com").role, UserRole.BARBER)

    def test_barber_signup_cannot_take_over_a_staff_account(self):
        self.authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/barbers/", {"shop": self.shop.id, "name": "x", "email": self.admin.email}, format="json"
        )
        self.assert_error(response)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, UserRole.ADMIN)

    def test_public_barber_list_hides_contact_details(self):
        response = self.client.get(f"/api/v1/barbers/?shop={self.shop.id}")
        details = self.assert_success(response)["data"][0]["user_details"]
        self.assertNotIn("email", details)
        self.assertNotIn("phone", details)

        self.authenticate(user=self.manager)
        response = self.client.get(f"/api/v1/barbers/?shop={self.shop.id}")
        self.assertIn("email", self.assert_success(response)["data"][0]["user_details"])


class ServiceRulesTests(ShopAccessTestCase):
    def test_customer_and_barber_cannot_change_services(self):
        for user in (self.customer, self.barber_user):
            self.authenticate(user=user)
            self.assert_error(self.client.delete(f"/api/v1/services/{self.service.id}/"), FORBIDDEN)
            self.assert_error(self.client.delete(f"/api/v1/categories/{self.category.id}/"), FORBIDDEN)
        self.assertTrue(Service.objects.filter(pk=self.service.id).exists())

    def test_manager_cannot_touch_another_shops_service(self):
        self.authenticate(user=self.manager)
        response = self.client.patch(f"/api/v1/services/{self.other_service.id}/", {"price": "1.00"}, format="json")
        self.assert_error(response, FORBIDDEN)

        response = self.client.post(
            "/api/v1/services/",
            {"shop": self.other_shop.id, "category": self.other_category.id, "name": "X", "price": "1.00"},
            format="json",
        )
        self.assert_error(response, FORBIDDEN)

    def test_service_category_must_belong_to_the_shop(self):
        self.authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/services/",
            {"shop": self.shop.id, "category": self.other_category.id, "name": "X", "price": "1.00"},
            format="json",
        )
        self.assert_error(response)


class BookingRulesTests(ShopAccessTestCase):
    def test_customer_sees_only_their_own_booking(self):
        self.authenticate(user=self.customer)
        self.assert_success(self.client.get(f"/api/v1/bookings/{self.booking.id}/"))

        self.authenticate(user=self.other_customer)
        self.assert_error(self.client.get(f"/api/v1/bookings/{self.booking.id}/"), FORBIDDEN)
        self.assert_error(self.client.post(f"/api/v1/bookings/{self.booking.id}/cancel/"), FORBIDDEN)

    def test_staff_from_another_shop_cannot_open_a_booking(self):
        for user in (self.other_manager, self.other_barber_user):
            self.authenticate(user=user)
            self.assert_error(self.client.get(f"/api/v1/bookings/{self.booking.id}/"), FORBIDDEN)

    def test_customer_cannot_mark_their_own_booking_paid(self):
        self.authenticate(user=self.customer)
        for body in ({"payment_status": "paid"}, {"status": "completed"}, {"tip_amount": "0.00"}):
            self.assert_error(self.client.patch(f"/api/v1/bookings/{self.booking.id}/", body, format="json"), FORBIDDEN)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status, "pending")

    def test_customer_can_still_reschedule_their_booking(self):
        self.authenticate(user=self.customer)
        response = self.client.patch(
            f"/api/v1/bookings/{self.booking.id}/", {"appointment_date": "2030-01-09"}, format="json"
        )
        self.assert_success(response)

    def test_customer_cannot_book_for_someone_else(self):
        self.authenticate(user=self.customer)
        payload = self.booking_payload(customer_id=str(self.other_customer.id))
        self.assert_error(self.client.post("/api/v1/bookings/", payload, format="json"), FORBIDDEN)

    def test_barber_and_services_must_belong_to_the_shop(self):
        self.authenticate(user=self.customer)
        response = self.client.post(
            "/api/v1/bookings/", self.booking_payload(barber=self.other_barber.id), format="json"
        )
        self.assert_error(response)
        response = self.client.post(
            "/api/v1/bookings/", self.booking_payload(services=[self.other_service.id]), format="json"
        )
        self.assert_error(response)

    def test_customer_cash_booking_is_confirmed_but_not_paid(self):
        self.authenticate(user=self.customer)
        response = self.client.post(
            "/api/v1/bookings/", self.booking_payload(payment_method="cash"), format="json"
        )
        booking = Booking.objects.get(pk=self.assert_success(response)["data"]["id"])
        self.assertEqual(booking.status, "confirmed")
        self.assertEqual(booking.payment_status, "pending")
        self.assertFalse(PaymentLog.objects.filter(booking=booking).exists())

    def test_staff_booking_never_opens_the_payment_gateway(self):
        self.shop.payment_gateway_enabled = True
        self.shop.save(update_fields=["payment_gateway_enabled"])
        self.authenticate(user=self.manager)
        payload = self.booking_payload(customer_id=str(self.customer.id), payment_method="cash")
        with mock.patch("apps.booking.views.requests.post") as stripe_call:
            response = self.client.post("/api/v1/bookings/", payload, format="json")
        self.assertIsNone(self.assert_success(response)["data"]["payment_url"])
        stripe_call.assert_not_called()

    def test_calendar_is_limited_to_the_users_shop(self):
        url = f"/api/v1/booking/?view_type=admin&shop_id={self.shop.id}&display_mode=calendar"
        for user in (self.customer, self.other_manager, self.other_barber_user):
            self.authenticate(user=user)
            self.assert_error(self.client.get(url), FORBIDDEN)
        for user in (self.admin, self.manager, self.barber_user):
            self.authenticate(user=user)
            self.assert_success(self.client.get(url))


class ClientAndDashboardRulesTests(ShopAccessTestCase):
    def test_every_customer_account_is_a_client(self):
        self.authenticate(user=self.manager)
        response = self.client.get(f"/api/v1/dashboard/shops/{self.shop.id}/clients/")
        emails = {client["email"] for client in self.assert_success(response)["data"]["all_clients"]}
        self.assertEqual(emails, {self.customer.email, self.other_customer.email})

    def test_barber_can_list_clients(self):
        self.authenticate(user=self.barber_user)
        self.assert_success(self.client.get("/api/v1/contact/list/"))

    def test_customer_cannot_read_admin_data(self):
        self.authenticate(user=self.customer)
        for url in (
            f"/api/v1/dashboard/shops/{self.shop.id}/clients/",
            f"/api/v1/dashboard/shops/{self.shop.id}/staff/",
            f"/api/v1/dashboard/shops/{self.shop.id}/client-groups/",
            f"/api/v1/dashboard/shops/{self.shop.id}/reviews/",
            f"/api/v1/dashboard/?shop={self.shop.id}",
            f"/api/v1/dashboard/reports/?shop={self.shop.id}",
            f"/api/v1/schedule/opening-calendar/?shop={self.shop.id}&date=2030-01-07",
            f"/api/v1/schedule/time-off/?shop={self.shop.id}",
            f"/api/v1/schedule/shifts/?shop={self.shop.id}",
            f"/api/v1/schedule/breaks/?shop={self.shop.id}",
            f"/api/v1/payments/manual/?shop={self.shop.id}",
        ):
            self.assert_error(self.client.get(url), FORBIDDEN)

    def test_manager_cannot_read_another_shop(self):
        self.authenticate(user=self.other_manager)
        for url in (
            f"/api/v1/dashboard/?shop={self.shop.id}",
            f"/api/v1/dashboard/reports/?shop={self.shop.id}",
            f"/api/v1/dashboard/shops/{self.shop.id}/staff/",
            f"/api/v1/schedule/opening-calendar/?shop={self.shop.id}&date=2030-01-07",
            f"/api/v1/payments/manual/?shop={self.shop.id}",
        ):
            self.assert_error(self.client.get(url), FORBIDDEN)

    def test_barber_cannot_message_clients_or_create_groups(self):
        self.authenticate(user=self.barber_user)
        url = f"/api/v1/dashboard/shops/{self.shop.id}"
        self.assert_error(self.client.post(f"{url}/send-messages/", {"group_id": 1}, format="json"), FORBIDDEN)
        self.assert_error(self.client.post(f"{url}/client-groups/", {"name": "VIP"}, format="json"), FORBIDDEN)

    def test_only_admins_broadcast_notifications(self):
        self.authenticate(user=self.manager)
        body = {"title": "Hello", "message": "World"}
        self.assert_error(self.client.post("/api/v1/notifications/send/", body, format="json"), FORBIDDEN)

    def test_payment_logs_stay_within_the_managers_shop(self):
        PaymentLog.objects.create(booking=self.booking, amount="30.00", method="cash")
        self.authenticate(user=self.other_manager)
        data = self.assert_success(self.client.get("/api/v1/payments/manual/"))["data"]
        self.assertEqual(data["appointment_count"], 0)

        response = self.client.post(
            "/api/v1/payments/manual/", {"booking_id": self.booking.id, "method": "cash"}, format="json"
        )
        self.assert_error(response, FORBIDDEN)


class ScheduleRulesTests(ShopAccessTestCase):
    def test_customer_cannot_change_business_hours(self):
        self.authenticate(user=self.customer)
        body = [{"day_of_week": "monday", "open_time": "01:00:00", "close_time": "02:00:00"}]
        response = self.client.put(f"/api/v1/schedule/business-hours/{self.shop.id}/", body, format="json")
        self.assert_error(response, FORBIDDEN)

    def test_customer_can_read_shop_hours(self):
        self.authenticate(user=self.customer)
        self.assert_success(self.client.get(f"/api/v1/schedule/business-hours/{self.shop.id}/"))

    def test_manager_cannot_change_another_shops_barber_schedule(self):
        self.authenticate(user=self.other_manager)
        body = {"barber": self.barber.id, "date": "2030-01-07", "shift": {"is_off": True}}
        self.assert_error(self.client.put("/api/v1/schedule/barber/schedule/", body, format="json"), FORBIDDEN)

    def test_barber_time_off_stays_pending_even_if_they_ask_for_approved(self):
        self.authenticate(user=self.barber_user)
        body = {"start_date": "2030-01-07", "end_date": "2030-01-07", "status": "approved"}
        response = self.client.post("/api/v1/schedule/time-off/", body, format="json")
        data = self.assert_success(response)["data"]
        self.assertEqual(data["status"], "pending")

    def test_barber_cannot_request_time_off_for_a_colleague(self):
        colleague = Barber.objects.create(
            user=self.create_user(email="colleague@example.com", role=UserRole.BARBER), shop=self.shop
        )
        self.authenticate(user=self.barber_user)
        body = {"barber": colleague.id, "start_date": "2030-01-07"}
        self.assert_error(self.client.post("/api/v1/schedule/time-off/", body, format="json"), FORBIDDEN)

    def test_manager_time_off_is_approved_automatically(self):
        self.authenticate(user=self.manager)
        body = {"barber": self.barber.id, "start_date": "2030-01-07"}
        response = self.client.post("/api/v1/schedule/time-off/", body, format="json")
        self.assertEqual(self.assert_success(response)["data"]["status"], "approved")

    def test_barber_cannot_approve_their_own_time_off(self):
        timeoff = BarberTimeOff.objects.create(
            barber=self.barber, start_date=datetime.date(2030, 1, 7), end_date=datetime.date(2030, 1, 7), reason="x"
        )
        self.authenticate(user=self.barber_user)
        self.assert_error(
            self.client.patch(
                f"/api/v1/schedule/time-off/{timeoff.id}/approval/", {"status": "approved"}, format="json"
            ),
            FORBIDDEN,
        )
        response = self.client.patch(f"/api/v1/schedule/time-off/{timeoff.id}/", {"status": "approved"}, format="json")
        self.assertEqual(self.assert_success(response)["data"]["status"], "pending")

    def test_other_shops_manager_cannot_approve_time_off(self):
        timeoff = BarberTimeOff.objects.create(
            barber=self.barber, start_date=datetime.date(2030, 1, 7), end_date=datetime.date(2030, 1, 7), reason="x"
        )
        self.authenticate(user=self.other_manager)
        response = self.client.patch(
            f"/api/v1/schedule/time-off/{timeoff.id}/approval/", {"status": "approved"}, format="json"
        )
        self.assert_error(response, FORBIDDEN)


class WebhookTests(ShopAccessTestCase):
    SECRET = "whsec_test"

    def stripe_event(self):
        return json.dumps(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"client_reference_id": self.booking.booking_code, "amount_total": 3000}},
            }
        )

    def post_stripe(self, payload, signature):
        return self.client.post(
            "/api/v1/payments/webhook/stripe/",
            payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=signature,
        )

    def sign(self, payload, timestamp=None):
        timestamp = timestamp or int(time.time())
        digest = hmac.new(self.SECRET.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
        return f"t={timestamp},v1={digest}"

    def assert_booking_paid(self, expected):
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.payment_status == "paid", expected)

    def test_unsigned_stripe_event_is_rejected(self):
        with mock.patch("config.env.STRIPE_WEBHOOK_SECRET", self.SECRET):
            response = self.post_stripe(self.stripe_event(), "")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_booking_paid(False)

    def test_forged_stripe_signature_is_rejected(self):
        payload = self.stripe_event()
        with mock.patch("config.env.STRIPE_WEBHOOK_SECRET", self.SECRET):
            response = self.post_stripe(payload, f"t={int(time.time())},v1={'0' * 64}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_booking_paid(False)

    def test_replayed_stripe_event_is_rejected(self):
        payload = self.stripe_event()
        with mock.patch("config.env.STRIPE_WEBHOOK_SECRET", self.SECRET):
            response = self.post_stripe(payload, self.sign(payload, timestamp=int(time.time()) - 3600))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_booking_paid(False)

    def test_stripe_event_is_rejected_when_no_secret_is_configured(self):
        payload = self.stripe_event()
        with mock.patch("config.env.STRIPE_WEBHOOK_SECRET", ""):
            response = self.post_stripe(payload, self.sign(payload))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assert_booking_paid(False)

    def test_correctly_signed_stripe_event_marks_the_booking_paid(self):
        payload = self.stripe_event()
        with mock.patch("config.env.STRIPE_WEBHOOK_SECRET", self.SECRET):
            response = self.post_stripe(payload, self.sign(payload))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_booking_paid(True)

    def test_revenuecat_webhook_requires_the_shared_secret(self):
        body = {"event": {"app_user_id": self.booking.booking_code, "price": 30}}
        with mock.patch("config.env.REVENUECAT_WEBHOOK_SECRET", self.SECRET):
            response = self.client.post("/api/v1/payments/webhook/revenuecat/", body, format="json")
            self.assertEqual(response.status_code, FORBIDDEN)
            self.assert_booking_paid(False)

            response = self.client.post(
                "/api/v1/payments/webhook/revenuecat/",
                body,
                format="json",
                HTTP_AUTHORIZATION=f"Bearer {self.SECRET}",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_booking_paid(True)
