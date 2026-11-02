"""Tests for booking creation and customer specification."""

import datetime
from decimal import Decimal

from apps.barber.models import Barber
from apps.booking.models import Booking
from apps.core.test_utils import BaseAPITestCase
from apps.service.models import Service, ServiceCategory
from apps.shop.models import Shop
from apps.user.enums import UserRole


class BookingCreateTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(email="owner@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Barberbay Studio",
            location="123 Main St",
            payment_gateway_enabled=False,
        )
        self.barber_user = self.create_user(email="barber@example.com", role="barber")
        self.barber = Barber.objects.create(
            user=self.barber_user,
            shop=self.shop,
            specialty="Master Barber",
        )
        self.category = ServiceCategory.objects.create(shop=self.shop, name="Haircuts")
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Classic Haircut",
            price="30.00",
            duration_minutes=30,
        )
        self.service.barbers.add(self.barber.user)
        self.customer = self.create_user(email="customer@example.com", role=UserRole.USER)
        
        # Add schedule to allow booking
        from apps.shop.models import BusinessHour
        from apps.schedule.models import BarberShift
        import datetime
        for day, _ in BusinessHour.DAY_CHOICES:
            BusinessHour.objects.create(shop=self.shop, day_of_week=day, open_time=datetime.time(8, 0), close_time=datetime.time(20, 0))
            BarberShift.objects.create(barber=self.barber, day_of_week=day, start_time=datetime.time(9, 0), end_time=datetime.time(19, 0))

    def test_customer_creates_booking_defaults_to_request_user(self):
        """When a customer creates booking without customer_id, customer is request.user."""
        self.authenticate(user=self.customer)

        payload = {
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-01",
            "start_time": "10:00:00",
            "payment_method": "cash",
        }
        res = self.client.post("/api/v1/bookings/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BOOKING_CREATED")
        booking_id = data["data"]["id"]

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.customer, self.customer)

    def test_admin_creates_booking_with_customer_id_payload(self):
        """When admin creates booking with customer_id in payload, customer is that user."""
        self.authenticate(user=self.owner)

        payload = {
            "customer_id": str(self.customer.id),
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-02",
            "start_time": "14:00:00",
            "payment_method": "cash",
            "discount": "5.00",
        }
        res = self.client.post("/api/v1/bookings/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BOOKING_CREATED")
        booking_id = data["data"]["id"]

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.customer, self.customer)
        self.assertEqual(booking.total_amount, Decimal("25.00"))
        self.assertEqual(booking.payment_status, "pending")
        self.assertEqual(booking.status, "confirmed")

    def test_admin_creates_booking_with_user_payload(self):
        """When admin creates booking with 'user' in payload, customer is that user."""
        self.authenticate(user=self.owner)

        payload = {
            "user": str(self.customer.id),
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-03",
            "start_time": "15:00:00",
            "payment_method": "cash",
        }
        res = self.client.post("/api/v1/bookings/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BOOKING_CREATED")
        booking_id = data["data"]["id"]

        booking = Booking.objects.get(pk=booking_id)
        self.assertEqual(booking.customer, self.customer)

    def test_booking_creation_without_payment_method_stays_pending(self):
        """When user or admin creates a booking without payment_method, it stays pending."""
        # 1. Admin creates booking without payment method
        self.authenticate(user=self.owner)
        payload = {
            "customer_id": str(self.customer.id),
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-04",
            "start_time": "16:00:00",
        }
        res = self.client.post("/api/v1/bookings/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BOOKING_CREATED")
        booking = Booking.objects.get(pk=data["data"]["id"])
        self.assertEqual(booking.payment_status, "pending")
        self.assertEqual(booking.status, "pending")

        # 2. Customer creates booking without payment method
        self.authenticate(user=self.customer)
        customer_payload = {
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-05",
            "start_time": "11:00:00",
        }
        res = self.client.post("/api/v1/bookings/", customer_payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BOOKING_CREATED")
        booking_cust = Booking.objects.get(pk=data["data"]["id"])
        self.assertEqual(booking_cust.payment_status, "pending")
        self.assertEqual(booking_cust.status, "pending")

    def test_booking_list_view_returns_7_day_range(self):
        """When admin requests the booking list view, it returns a 7-day range of date-grouped dictionaries."""
        self.authenticate(user=self.owner)

        # Create a booking on target_date (2037-09-07)
        payload = {
            "customer_id": str(self.customer.id),
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": "2037-09-07",
            "start_time": "12:00:00",
            "payment_method": "cash",
        }
        self.client.post("/api/v1/bookings/", payload, format="json")

        # Request list view with date=2037-09-07
        res = self.client.get(
            f"/api/v1/booking/?view_type=admin&shop_id={self.shop.id}&date=2037-09-07&display_mode=list"
        )
        data = self.assert_success(res)
        self.assertEqual(data["code"], "LIST_VIEW")
        
        dates_returned = [item["date"] for item in data["data"]]
        # We expect formatted date strings like "Thu, 03 September"
        self.assertTrue(any("03 September" in d for d in dates_returned))
        self.assertTrue(any("07 September" in d for d in dates_returned))
        self.assertTrue(any("09 September" in d for d in dates_returned))
        self.assertFalse(any("10 September" in d for d in dates_returned))
        
        # Check target date info
        target_day_data = next((item for item in data["data"] if "07 September" in item["date"]), None)
        self.assertIsNotNone(target_day_data)
        self.assertEqual(target_day_data["appointment_count"], 1)
        self.assertEqual(target_day_data["total_ammount"], 30.0)
        self.assertEqual(target_day_data["appointment_count"], 1)
        self.assertEqual(len(target_day_data["appointments"]), 1)
