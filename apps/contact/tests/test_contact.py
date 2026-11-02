"""Tests for contact endpoints."""

from rest_framework import status

from apps.core.test_utils import BaseAPITestCase


class ContactTests(BaseAPITestCase):
    """Test contact form submission and customer user creation."""

    def test_submit_contact_form(self):
        """Public users can submit the contact form, but it never creates an account."""
        from apps.contact.models import ContactMessage
        from apps.user.models import User

        response = self.client.post(
            "/api/v1/contact/",
            {
                "full_name": "John Doe",
                "email": "john@example.com",
                "message": "Hello, I have a question.",
            },
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["data"]["email"], "john@example.com")
        self.assertTrue(ContactMessage.objects.filter(email="john@example.com").exists())
        self.assertFalse(User.objects.filter(email="john@example.com").exists())

    def test_shop_staff_can_create_customer(self):
        """Shop staff can add a customer account, which always gets the USER role."""
        from apps.user.enums import UserRole

        admin = self.create_user(email="admin@barberbay.com", role=UserRole.ADMIN)
        self.authenticate(user=admin)
        response = self.client.post(
            "/api/v1/contact/",
            {"full_name": "John Doe", "email": "john@example.com", "role": "ADMIN"},
        )
        data = self.assert_success(response, status.HTTP_201_CREATED)
        self.assertEqual(data["data"]["role"], "USER")

    def test_list_contacts_requires_admin(self):
        """Non-admin users cannot list contacts."""
        self.authenticate()  # Regular user
        response = self.client.get("/api/v1/contact/list/")
        self.assert_error(response, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_all_customer_contacts(self):
        """Admin can list all contacts with role USER."""
        from apps.user.enums import UserRole
        from apps.user.models import User

        admin = self.create_user(email="admin@barberbay.com", role=UserRole.ADMIN)
        self.create_user(email="client1@example.com", full_name="Client One", role=UserRole.USER)
        self.create_user(email="client2@example.com", full_name="Client Two", role=UserRole.USER)

        self.authenticate(user=admin)
        response = self.client.get("/api/v1/contact/list/")
        data = self.assert_success(response)
        self.assertEqual(data["code"], "CONTACTS_RETRIEVED")
        emails = [c["email"] for c in data["data"]]
        self.assertIn("client1@example.com", emails)
        self.assertIn("client2@example.com", emails)
        # Admin themselves should not be listed as role is ADMIN
        self.assertNotIn("admin@barberbay.com", emails)


class FAQTests(BaseAPITestCase):
    """Test FAQ endpoints."""

    def test_list_faqs_public(self):
        """Anyone can list FAQs."""
        response = self.client.get("/api/v1/faqs/")
        self.assert_success(response)

    def test_create_faq_requires_admin(self):
        """Only admins can create FAQs."""
        self.authenticate()  # Regular user
        response = self.client.post(
            "/api/v1/faqs/",
            {
                "question": "Test?",
                "answer": "Yes.",
            },
        )
        self.assert_error(response, status.HTTP_403_FORBIDDEN)
