"""Tests for user login and role-based shop list."""

from apps.barber.models import Barber
from apps.core.test_utils import BaseAPITestCase
from apps.shop.models import Shop
from apps.user.enums import UserRole


class LoginShopListTests(BaseAPITestCase):
    """Test user login returns assigned shops for admin/staff/barber."""

    def setUp(self):
        super().setUp()
        self.owner = self.create_user(email="owner@example.com", role=UserRole.ADMIN)
        self.shop1 = Shop.objects.create(
            owner=self.owner,
            name="Downtown Barber Studio",
            location="123 Main St",
            phone="+1234567890",
            email="shop1@example.com",
        )
        self.shop2 = Shop.objects.create(
            owner=self.owner,
            name="Uptown Luxury Salon",
            location="456 High St",
            phone="+1987654321",
            email="shop2@example.com",
        )

    def test_regular_user_login_has_empty_shops(self):
        """Regular customer login should return empty shops list."""
        self.create_user(email="customer@example.com", password="Password123!", role=UserRole.USER)
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "customer@example.com", "password": "Password123!"},
        )
        data = self.assert_success(response)
        self.assertEqual(data["data"]["user"]["role"], "USER")
        self.assertEqual(data["data"]["user"]["shops"], [])
        self.assertEqual(data["data"]["shops"], [])

    def test_admin_login_returns_all_shops(self):
        """Admin login should return all shops in the platform."""
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "owner@example.com", "password": "TestPass123!"},
        )
        data = self.assert_success(response)
        self.assertEqual(data["data"]["user"]["role"], "ADMIN")
        shops = data["data"]["shops"]
        self.assertEqual(len(shops), 2)
        shop_names = [s["name"] for s in shops]
        self.assertIn("Downtown Barber Studio", shop_names)
        self.assertIn("Uptown Luxury Salon", shop_names)
        self.assertEqual(data["data"]["user"]["shops"], shops)

    def test_barber_login_returns_assigned_shop(self):
        """Barber / Staff login should return only the assigned shop."""
        barber_user = self.create_user(email="barber@example.com", password="Password123!", role="barber")
        Barber.objects.create(user=barber_user, shop=self.shop1, specialty="Senior Stylist")

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "barber@example.com", "password": "Password123!"},
        )
        data = self.assert_success(response)
        shops = data["data"]["shops"]
        self.assertEqual(len(shops), 1)
        self.assertEqual(shops[0]["id"], self.shop1.id)
        self.assertEqual(shops[0]["name"], "Downtown Barber Studio")

    def test_admin_profile_endpoint_returns_shops(self):
        """GET /auth/profile/ should also include shops for admin."""
        self.authenticate(user=self.owner)
        response = self.client.get("/api/v1/auth/profile/")
        data = self.assert_success(response)
        self.assertEqual(len(data["data"]["shops"]), 2)

