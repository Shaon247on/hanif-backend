from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.barber.models import Barber
from apps.service.models import Service, ServiceCategory
from apps.shop.models import Shop
from apps.user.enums import UserRole

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="smtp@barberbay.com",
)
class BarberAPITests(APITestCase):
    def setUp(self):
        # Create Owner/Admin user and authenticate
        self.admin_user = User.objects.create_user(
            username="adminuser", email="admin@example.com", password="password123", role=UserRole.ADMIN
        )
        self.client.force_authenticate(user=self.admin_user)

        # Create a Shop
        self.shop = Shop.objects.create(
            name="Test Shop",
            location="Dhaka",
            owner=self.admin_user,
        )

        # Create Service Category and Services
        self.category = ServiceCategory.objects.create(
            shop=self.shop,
            name="Haircut",
        )
        self.service1 = Service.objects.create(
            category=self.category,
            shop=self.shop,
            name="Classic Fade",
            price=20.00,
            duration_minutes=30,
        )
        self.service2 = Service.objects.create(
            category=self.category,
            shop=self.shop,
            name="Beard Trim",
            price=15.00,
            duration_minutes=15,
        )

    def test_create_barber_staff(self):
        url = "/api/v1/barbers/"
        data = {
            "shop": self.shop.id,
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+123456789",
            "specialty": "Senior Barber",
            "role": "staff",
            "calendar_access": True,
            "client_details_access": False,
            "services": [self.service1.id, self.service2.id],
        }

        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])

        # Check Barber model exists
        barber = Barber.objects.get(specialty="Senior Barber")
        self.assertEqual(barber.role, "staff")
        self.assertEqual(barber.calendar_access, True)
        self.assertEqual(barber.client_details_access, False)

        # Check associated User was created
        user = barber.user
        self.assertEqual(user.full_name, "Jane Doe")
        self.assertEqual(user.email, "jane@example.com")
        self.assertEqual(user.phone, "+123456789")
        self.assertTrue(user.is_active)
        self.assertEqual(user.status, 1)
        self.assertEqual(user.role, "BARBER")

        # Check many-to-many services relationship
        self.assertIn(user, self.service1.barbers.all())
        self.assertIn(user, self.service2.barbers.all())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Login Email: jane@example.com", mail.outbox[0].body)
        self.assertIn("Temporary Password:", mail.outbox[0].body)
        self.assertIn("Welcome to the team", mail.outbox[0].alternatives[0][0])
        self.assertIn("Login email", mail.outbox[0].alternatives[0][0])

    def test_create_duplicate_barber_email_returns_validation_error(self):
        user = User.objects.create_user(
            username="existingbarber",
            email="existing@example.com",
            password="Password123!",
        )
        Barber.objects.create(user=user, shop=self.shop)

        response = self.client.post(
            "/api/v1/barbers/",
            {
                "shop": self.shop.id,
                "name": "Another Barber",
                "email": "existing@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(response.data["details"]))

    def test_update_barber_staff(self):
        # Create initial barber
        user = User.objects.create(
            email="testbarber@example.com",
            full_name="Old Name",
            phone="111",
        )
        user.set_unique_username()
        user.save()

        barber = Barber.objects.create(
            user=user,
            shop=self.shop,
            specialty="Junior Barber",
            role="staff",
            calendar_access=True,
            client_details_access=True,
        )
        self.service1.barbers.add(user)

        url = f"/api/v1/barbers/{barber.id}/"
        data = {
            "name": "New Name",
            "phone": "222",
            "role": "admin",
            "calendar_access": False,
            "services": [self.service2.id],  # Swapping services
        }

        response = self.client.put(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        barber.refresh_from_db()
        user.refresh_from_db()

        self.assertEqual(user.full_name, "New Name")
        self.assertEqual(user.phone, "222")
        self.assertEqual(barber.role, "admin")
        self.assertEqual(barber.calendar_access, False)

        # Check updated services
        self.assertNotIn(user, self.service1.barbers.all())
        self.assertIn(user, self.service2.barbers.all())
