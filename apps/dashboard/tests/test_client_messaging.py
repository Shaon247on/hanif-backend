"""Client groups and one-way messaging: the permission table from the business brief."""

import datetime

from rest_framework import status

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking
from apps.core.test_utils import BaseAPITestCase
from apps.notification.models import Notification
from apps.service.models import Service, ServiceCategory
from apps.shop.models import ClientGroup, ClientMessage, Shop
from apps.user.enums import UserRole

FORBIDDEN = status.HTTP_403_FORBIDDEN


class MessagingTestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=self.admin, name="Shop A", location="A")
        self.other_shop = Shop.objects.create(owner=self.admin, name="Shop B", location="B")
        self.manager = self.create_user(email="manager@example.com", role=UserRole.MANAGER)
        self.shop.managers.add(self.manager)
        self.other_manager = self.create_user(email="manager2@example.com", role=UserRole.MANAGER)
        self.other_shop.managers.add(self.other_manager)
        self.barber_user = self.create_user(email="barber@example.com", role=UserRole.BARBER)
        self.barber = Barber.objects.create(user=self.barber_user, shop=self.shop)
        self.member = self.create_user(email="member@example.com", full_name="Member", role=UserRole.USER)
        self.outsider = self.create_user(email="outsider@example.com", full_name="Outsider", role=UserRole.USER)

        self.group = ClientGroup.objects.create(shop=self.shop, name="VIP")
        self.group.clients.add(self.member)
        self.base = f"/api/v1/dashboard/shops/{self.shop.id}"

    def send_to_group(self, body="Hello"):
        return self.client.post(f"{self.base}/client-groups/{self.group.id}/messages/", {"body": body}, format="json")


class ClientGroupTests(MessagingTestCase):
    def test_only_created_groups_are_listed(self):
        self.authenticate(user=self.manager)
        groups = self.assert_success(self.client.get(f"{self.base}/client-groups/"))["data"]
        self.assertEqual([(group["name"], group["member_count"]) for group in groups], [("VIP", 1)])

    def test_manager_creates_a_group_from_selected_clients(self):
        self.authenticate(user=self.manager)
        body = {"name": "Weekend", "clients": [str(self.member.id), str(self.outsider.id)]}
        data = self.assert_success(self.client.post(f"{self.base}/client-groups/", body, format="json"))["data"]
        self.assertEqual(data["member_count"], 2)
        self.assertEqual(len(data["members"]), 2)

    def test_group_needs_a_name_and_clients_and_a_unique_name(self):
        self.authenticate(user=self.manager)
        url = f"{self.base}/client-groups/"
        clients = [str(self.member.id)]
        self.assert_error(self.client.post(url, {"name": "", "clients": clients}, format="json"))
        self.assert_error(self.client.post(url, {"name": "New", "clients": []}, format="json"))
        self.assert_error(self.client.post(url, {"name": "vip", "clients": clients}, format="json"))

    def test_staff_accounts_cannot_be_added_as_group_clients(self):
        self.authenticate(user=self.manager)
        body = {"name": "Mixed", "clients": [str(self.member.id), str(self.barber_user.id)]}
        data = self.assert_success(self.client.post(f"{self.base}/client-groups/", body, format="json"))["data"]
        self.assertEqual(data["member_count"], 1)

    def test_barber_and_customer_cannot_create_or_change_groups(self):
        body = {"name": "Nope", "clients": [str(self.member.id)]}
        for user in (self.barber_user, self.member):
            self.authenticate(user=user)
            self.assert_error(self.client.post(f"{self.base}/client-groups/", body, format="json"), FORBIDDEN)
            url = f"{self.base}/client-groups/{self.group.id}/"
            self.assert_error(self.client.patch(url, {"name": "X"}, format="json"), FORBIDDEN)
            self.assert_error(self.client.delete(url), FORBIDDEN)

    def test_manager_can_rename_change_members_and_delete(self):
        self.authenticate(user=self.manager)
        url = f"{self.base}/client-groups/{self.group.id}/"
        body = {"name": "Gold", "clients": [str(self.outsider.id)]}
        data = self.assert_success(self.client.patch(url, body, format="json"))["data"]
        self.assertEqual(data["name"], "Gold")
        self.assertEqual([member["email"] for member in data["members"]], [self.outsider.email])

        self.assert_success(self.client.delete(url))
        self.assertFalse(ClientGroup.objects.filter(pk=self.group.pk).exists())

    def test_another_shops_manager_is_blocked(self):
        self.authenticate(user=self.other_manager)
        self.assert_error(self.client.get(f"{self.base}/client-groups/"), FORBIDDEN)
        self.assert_error(self.client.get(f"{self.base}/client-groups/{self.group.id}/messages/"), FORBIDDEN)
        self.assert_error(self.send_to_group(), FORBIDDEN)


class GroupMessagingTests(MessagingTestCase):
    def test_admin_and_manager_can_send(self):
        for user in (self.admin, self.manager):
            self.authenticate(user=user)
            self.assert_success(self.send_to_group())
        self.assertEqual(ClientMessage.objects.filter(group=self.group).count(), 2)

    def test_barber_and_customer_cannot_send(self):
        for user in (self.barber_user, self.member):
            self.authenticate(user=user)
            self.assert_error(self.send_to_group(), FORBIDDEN)
        self.assertFalse(ClientMessage.objects.exists())

    def test_barber_reads_history_but_cannot_send(self):
        self.authenticate(user=self.manager)
        self.send_to_group("Sale on Friday")

        self.authenticate(user=self.barber_user)
        data = self.assert_success(self.client.get(f"{self.base}/client-groups/{self.group.id}/messages/"))["data"]
        self.assertFalse(data["can_send"])
        self.assertEqual(data["messages"][0]["body"], "Sale on Friday")

    def test_member_reads_the_group_and_outsider_does_not(self):
        self.authenticate(user=self.manager)
        self.send_to_group("Sale on Friday")

        self.authenticate(user=self.member)
        data = self.assert_success(self.client.get(f"/api/v1/dashboard/my-messages/groups/{self.group.id}/"))["data"]
        self.assertFalse(data["can_send"])
        self.assertEqual(data["messages"][0]["body"], "Sale on Friday")
        self.assertNotIn("members", data["group"])

        self.authenticate(user=self.outsider)
        self.assert_error(self.client.get(f"/api/v1/dashboard/my-messages/groups/{self.group.id}/"), FORBIDDEN)

    def test_customer_sees_only_their_own_conversations(self):
        self.authenticate(user=self.manager)
        self.send_to_group("Sale")

        self.authenticate(user=self.member)
        conversations = self.assert_success(self.client.get("/api/v1/dashboard/my-messages/"))["data"]
        self.assertEqual([item["name"] for item in conversations], ["VIP"])
        self.assertEqual(conversations[0]["last_message"]["body"], "Sale")

        self.authenticate(user=self.outsider)
        self.assertEqual(self.assert_success(self.client.get("/api/v1/dashboard/my-messages/"))["data"], [])

    def test_members_are_notified_in_the_app(self):
        self.authenticate(user=self.manager)
        self.send_to_group("Sale on Friday")
        notification = Notification.objects.get(user=self.member)
        self.assertEqual(notification.title, "New message from Shop A")
        self.assertEqual(notification.message, "Sale on Friday")

    def test_history_survives_a_member_leaving(self):
        self.authenticate(user=self.manager)
        self.send_to_group("Before leaving")
        self.group.clients.remove(self.member)
        self.assertEqual(ClientMessage.objects.filter(group=self.group).count(), 1)

    def test_empty_message_is_rejected(self):
        self.authenticate(user=self.manager)
        self.assert_error(self.send_to_group("   "))


class DirectMessagingTests(MessagingTestCase):
    def url(self, client=None):
        return f"{self.base}/clients/{(client or self.member).id}/messages/"

    def test_manager_messages_one_client(self):
        self.authenticate(user=self.manager)
        self.assert_success(self.client.post(self.url(), {"body": "Your order is ready"}, format="json"))

        self.authenticate(user=self.member)
        conversations = self.assert_success(self.client.get("/api/v1/dashboard/my-messages/"))["data"]
        direct = next(item for item in conversations if item["type"] == "direct")
        self.assertEqual(direct["name"], "Shop A")

        thread = self.client.get(f"/api/v1/dashboard/my-messages/shops/{self.shop.id}/")
        self.assertEqual(self.assert_success(thread)["data"]["messages"][0]["body"], "Your order is ready")

    def test_a_customer_cannot_read_another_customers_direct_messages(self):
        self.authenticate(user=self.manager)
        self.client.post(self.url(), {"body": "Private"}, format="json")

        self.authenticate(user=self.outsider)
        self.assert_error(self.client.get(self.url()), FORBIDDEN)
        thread = self.client.get(f"/api/v1/dashboard/my-messages/shops/{self.shop.id}/")
        self.assertEqual(self.assert_success(thread)["data"]["messages"], [])

    def test_barber_and_customer_cannot_send_directly(self):
        for user in (self.barber_user, self.member):
            self.authenticate(user=user)
            self.assert_error(self.client.post(self.url(), {"body": "x"}, format="json"), FORBIDDEN)

    def test_cannot_message_a_staff_account_as_a_client(self):
        self.authenticate(user=self.manager)
        response = self.client.post(self.url(self.barber_user), {"body": "x"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ClientDetailsTests(MessagingTestCase):
    def test_details_show_the_clients_bookings(self):
        category = ServiceCategory.objects.create(shop=self.shop, name="Hair")
        service = Service.objects.create(
            shop=self.shop, category=category, name="Cut", price="30.00", duration_minutes=30
        )
        booking = Booking.objects.create(
            booking_code="BB-1", customer=self.member, shop=self.shop, total_amount="30.00", status="completed"
        )
        Appointment.objects.create(
            booking=booking,
            service=service,
            barber=self.barber,
            appointment_date=datetime.date(2026, 1, 5),
            start_time=datetime.time(10),
            end_time=datetime.time(10, 30),
            price="30.00",
            status="completed",
        )

        self.authenticate(user=self.manager)
        data = self.assert_success(self.client.get(f"{self.base}/clients/{self.member.id}/"))["data"]
        self.assertEqual(data["client"]["email"], self.member.email)
        self.assertEqual(data["past_bookings"][0]["booking_code"], "BB-1")
        self.assertEqual(data["metrics"]["total_appointments"], 1)
