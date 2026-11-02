"""Simultaneous requests against the real database, which TestCase transactions cannot exercise."""

import datetime
import threading

from django.db import connection
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.barber.models import Barber
from apps.booking.models import Appointment
from apps.schedule.models import BarberShift
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessHour, Shop
from apps.user.enums import UserRole
from apps.user.models import User

REQUEST_COUNT = 8


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ConcurrentBookingTests(TransactionTestCase):
    def setUp(self):
        owner = User.objects.create(email="o@example.com", username="o", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=owner, name="Shop", location="Dhaka")
        barber_user = User.objects.create(email="b@example.com", username="b", role=UserRole.BARBER)
        self.barber = Barber.objects.create(user=barber_user, shop=self.shop)
        category = ServiceCategory.objects.create(shop=self.shop, name="Hair")
        self.service = Service.objects.create(
            shop=self.shop, category=category, name="Cut", price="30.00", duration_minutes=30
        )
        for day, _ in BusinessHour.DAY_CHOICES:
            BusinessHour.objects.create(
                shop=self.shop, day_of_week=day, open_time=datetime.time(9), close_time=datetime.time(21)
            )
            BarberShift.objects.create(
                barber=self.barber, day_of_week=day, start_time=datetime.time(9), end_time=datetime.time(21)
            )
        self.customers = [
            User.objects.create(email=f"c{index}@example.com", username=f"c{index}", role=UserRole.USER)
            for index in range(REQUEST_COUNT)
        ]

    def test_only_one_of_many_simultaneous_requests_gets_the_slot(self):
        barrier = threading.Barrier(REQUEST_COUNT)
        status_codes = []

        def book(customer):
            client = APIClient()
            client.force_authenticate(user=customer)
            barrier.wait()
            try:
                response = client.post(
                    "/api/v1/bookings/",
                    {
                        "shop": self.shop.id,
                        "barber": self.barber.id,
                        "services": [self.service.id],
                        "appointment_date": "2037-11-04",
                        "start_time": "10:00:00",
                    },
                    format="json",
                )
                status_codes.append(response.status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=book, args=(customer,)) for customer in self.customers]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(status_codes), [200] + [400] * (REQUEST_COUNT - 1))
        self.assertEqual(Appointment.objects.filter(barber=self.barber).count(), 1)
