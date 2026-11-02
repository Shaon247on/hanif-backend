from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.shop.models import Shop
from apps.user.enums import UserRole
from apps.user.models import User


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="smtp@barberbay.com",
)
class DashboardStaffEmailTests(APITestCase):
    def test_create_staff_emails_login_credentials(self):
        admin = User.objects.create_user(
            username="admin",
            email="admin@barberbay.com",
            password="AdminPass123!",
            role=UserRole.ADMIN,
        )
        shop = Shop.objects.create(name="Test Shop", location="Dhaka", owner=admin)
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            f"/api/v1/dashboard/shops/{shop.id}/staff/",
            {
                "name": "Jane Doe",
                "email": "jane@barberbay.com",
                "position": "Senior Barber",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "smtp@barberbay.com")
        self.assertIn("Login Email: jane@barberbay.com", mail.outbox[0].body)
        self.assertIn(f"Temporary Password: {response.data['data']['password']}", mail.outbox[0].body)
