"""Tests for shop app."""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from apps.core.test_utils import BaseAPITestCase
from apps.shop.models import Shop, ShopGallery


class ShopAPITests(BaseAPITestCase):
    """Test cases for Shop and ShopGallery APIs."""

    def setUp(self):
        super().setUp()
        self.user = self.authenticate()
        self.user.role = "ADMIN"
        self.user.save()
        self.shop = Shop.objects.create(
            owner=self.user,
            name="Salon de Test",
            location="Testville",
        )

    def test_create_shop_success(self):
        """Authenticated user can create a shop."""
        response = self.client.post(
            "/api/v1/shops/",
            {
                "name": "Barber Palace",
                "location": "Banani, Dhaka",
            },
        )
        data = self.assert_success(response, status.HTTP_200_OK)
        self.assertEqual(data["data"]["name"], "Barber Palace")
        self.assertIsNotNone(data["data"]["slug"])

    def test_upload_multiple_gallery_images(self):
        """Authenticated user can upload multiple gallery images in a single request."""
        # Create small test images in memory
        images = []
        for i in range(3):
            file_obj = io.BytesIO()
            img = Image.new("RGBA", size=(50, 50), color=(i * 50, 100, 100))
            img.save(file_obj, "png")
            file_obj.seek(0)
            images.append(SimpleUploadedFile(f"test_{i}.png", file_obj.read(), content_type="image/png"))

        response = self.client.post(
            "/api/v1/shops/gallery/",
            {
                "shop": self.shop.id,
                "images": images,
                "display_order": [1, 2, 3],
            },
            format="multipart",
        )
        data = self.assert_success(response, status.HTTP_200_OK)
        self.assertEqual(len(data["data"]), 3)
        self.assertEqual(ShopGallery.objects.filter(shop=self.shop).count(), 3)
        # Verify order was saved correctly
        orders = [item["display_order"] for item in data["data"]]
        self.assertEqual(orders, [1, 2, 3])

    def test_google_review_create_returns_review_link(self):
        """POST returns the URL where a customer can submit a Google review."""
        self.shop.google_review_link = "https://g.page/r/example/review"
        self.shop.save(update_fields=["google_review_link"])

        response = self.client.post(f"/api/v1/shops/{self.shop.id}/google-reviews/", {}, format="json")

        data = self.assert_success(response, status.HTTP_200_OK)
        self.assertEqual(data["code"], "GOOGLE_REVIEW_CREATE_LINK")
        self.assertEqual(data["data"]["review_url"], self.shop.google_review_link)

    def test_google_review_create_requires_configured_link(self):
        """POST returns a clear error when the shop has no Google review URL."""
        response = self.client.post(f"/api/v1/shops/{self.shop.id}/google-reviews/", {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "MISSING_REVIEW_LINK")
