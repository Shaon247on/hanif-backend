from django.test import TestCase
from rest_framework.test import APIClient

from apps.user.models import User


class ManualPaymentLogQueryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="AdminPass123!",
            role="ADMIN",
            status=1,
        )
        self.client.force_authenticate(user=admin)

    def test_invalid_shop_query_returns_bad_request(self):
        response = self.client.get("/api/v1/payments/manual/?shop=9$duration_type=daily")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_SHOP_ID")
