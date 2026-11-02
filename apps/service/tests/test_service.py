"""Tests for service categories and the category-grouped service list."""

from apps.core.test_utils import BaseAPITestCase
from apps.service.models import Service, ServiceCategory
from apps.shop.models import Shop
from apps.user.enums import UserRole


class ServiceCategoryTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=self.admin, name="Shop", location="Dhaka")
        self.category = ServiceCategory.objects.create(shop=self.shop, name="Haircuts")
        self.authenticate(user=self.admin)

    def test_service_list_includes_its_category(self):
        Service.objects.create(shop=self.shop, category=self.category, name="Fade", price="20.00")
        data = self.assert_success(self.client.get(f"/api/v1/services/?shop={self.shop.id}"))["data"]
        self.assertEqual(data[0]["category"], {"id": self.category.id, "name": "Haircuts"})

    def test_category_name_cannot_be_duplicated_within_a_shop(self):
        body = {"shop": self.shop.id, "name": " haircuts "}
        self.assert_error(self.client.post("/api/v1/categories/", body, format="json"))
        self.assertEqual(ServiceCategory.objects.filter(shop=self.shop).count(), 1)

    def test_another_shop_can_use_the_same_category_name(self):
        other = Shop.objects.create(owner=self.admin, name="Other", location="Dhaka")
        body = {"shop": other.id, "name": "Haircuts"}
        self.assert_success(self.client.post("/api/v1/categories/", body, format="json"))

    def test_editing_a_service_uses_patch(self):
        service = Service.objects.create(shop=self.shop, category=self.category, name="Fade", price="20.00")
        response = self.client.patch(f"/api/v1/services/{service.id}/", {"price": "25.00"}, format="json")
        self.assert_success(response)
        service.refresh_from_db()
        self.assertEqual(str(service.price), "25.00")

    def test_deleting_a_service(self):
        service = Service.objects.create(shop=self.shop, category=self.category, name="Fade", price="20.00")
        self.assert_success(self.client.delete(f"/api/v1/services/{service.id}/"))
        self.assertFalse(Service.objects.filter(pk=service.pk).exists())