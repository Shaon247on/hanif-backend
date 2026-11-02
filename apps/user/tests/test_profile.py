"""Tests for user profile."""

from rest_framework import status

from apps.core.test_utils import BaseAPITestCase


class ProfileTests(BaseAPITestCase):
    """Test user profile endpoints."""

    def test_get_profile_authenticated(self):
        """Authenticated user can retrieve profile."""
        user = self.authenticate()
        response = self.client.get("/api/v1/auth/profile/")
        data = self.assert_success(response)
        self.assertEqual(data["data"]["email"], user.email)

    def test_get_profile_unauthenticated(self):
        """Unauthenticated request returns 401."""
        response = self.client.get("/api/v1/auth/profile/")
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_update_profile(self):
        """Authenticated user can update profile."""
        self.authenticate()
        response = self.client.patch(
            "/api/v1/auth/profile/update/",
            {"full_name": "Updated Name"},
        )
        data = self.assert_success(response)
        self.assertEqual(data["data"]["full_name"], "Updated Name")

    def test_update_profile_with_image(self):
        """Authenticated user can update profile including image."""
        self.authenticate()

        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        file_obj = io.BytesIO()
        img = Image.new("RGBA", size=(100, 100), color=(255, 0, 0))
        img.save(file_obj, "png")
        file_obj.seek(0)
        uploaded_image = SimpleUploadedFile("test.png", file_obj.read(), content_type="image/png")

        response = self.client.patch(
            "/api/v1/auth/profile/update/",
            {
                "full_name": "Image Name",
                "image": uploaded_image,
            },
            format="multipart",
        )
        data = self.assert_success(response)
        self.assertEqual(data["data"]["full_name"], "Image Name")
        self.assertIsNotNone(data["data"]["image"])

    def test_get_location_unauthenticated(self):
        """Unauthenticated request to location returns 401."""
        response = self.client.get("/api/v1/auth/profile/location/")
        self.assert_error(response, status.HTTP_401_UNAUTHORIZED)

    def test_get_location_not_found(self):
        """Retrieving location when not set returns data=None."""
        self.authenticate()
        response = self.client.get("/api/v1/auth/profile/location/")
        data = self.assert_success(response)
        self.assertIsNone(data.get("data"))

    def test_create_or_update_location(self):
        """User can create and update their unique location service."""
        self.authenticate()

        # Create location
        payload = {"location_name": "Salon A", "location_link": "https://maps.google.com"}
        response = self.client.post("/api/v1/auth/profile/location/", payload)
        data = self.assert_success(response)
        self.assertEqual(data["data"]["location_name"], "Salon A")
        self.assertEqual(data["data"]["location_link"], "https://maps.google.com")

        # Get location
        response = self.client.get("/api/v1/auth/profile/location/")
        data = self.assert_success(response)
        self.assertEqual(data["data"]["location_name"], "Salon A")

        # Update location
        update_payload = {"location_name": "Salon B", "location_link": "https://maps.google.com/updated"}
        response = self.client.put("/api/v1/auth/profile/location/", update_payload)
        data = self.assert_success(response)
        self.assertEqual(data["data"]["location_name"], "Salon B")
        self.assertEqual(data["data"]["location_link"], "https://maps.google.com/updated")

        # Verify update persisted
        response = self.client.get("/api/v1/auth/profile/location/")
        data = self.assert_success(response)
        self.assertEqual(data["data"]["location_name"], "Salon B")
