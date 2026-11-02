"""
Client groups and one-way messaging.

Admins and a shop's manager send; the shop's barbers read; customers read only the groups
they belong to and the messages addressed to them. Every rule is enforced here, not in the app.
"""

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from apps.core.access import can_access_shop, can_manage_shop, require_access_shop, require_manage_shop
from apps.core.permissions import IsActiveUser, IsShopStaff
from apps.core.responses import error_response, success_response
from apps.notification.utils import send_push_and_email
from apps.shop.models import ClientGroup, ClientMessage, Shop
from apps.user.enums import UserRole
from apps.user.models import User

MESSAGE_HISTORY_LIMIT = 200
NOTIFICATION_PREVIEW_LENGTH = 100


def serialize_message(message):
    sender = message.sender
    return {
        "id": message.id,
        "body": message.body,
        "created_at": message.created_at,
        "sender": {"id": sender.id, "name": sender.full_name or sender.username} if sender else None,
    }


def serialize_thread(messages):
    recent = messages.select_related("sender").order_by("-created_at")[:MESSAGE_HISTORY_LIMIT]
    return [serialize_message(message) for message in reversed(recent)]


def serialize_member(request, user):
    return {
        "id": user.id,
        "full_name": user.full_name or user.username,
        "email": user.email,
        "phone": user.phone,
        "image": request.build_absolute_uri(user.image.url) if user.image else None,
    }


def serialize_group(group):
    last_message = group.messages.order_by("-created_at").first()
    return {
        "id": group.id,
        "name": group.name,
        "member_count": group.clients.count(),
        "last_message": serialize_message(last_message) if last_message else None,
        "created_at": group.created_at,
    }


def serialize_group_detail(request, group):
    return {
        **serialize_group(group),
        "members": [serialize_member(request, user) for user in group.clients.all()],
    }


def get_clients(client_ids):
    return User.objects.filter(id__in=client_ids, role=UserRole.USER)


def get_message_body(request):
    return (request.data.get("body") or "").strip()


def notify_clients(shop, clients, body):
    preview = body[:NOTIFICATION_PREVIEW_LENGTH]
    for client in clients:
        send_push_and_email(
            user=client, title=f"New message from {shop.name}", message=preview, notif_type="system", send_email=False
        )


class ClientGroupListCreateAPIView(APIView):
    """GET: The shop's real client groups. POST: Create one from existing customers."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, *args, **kwargs):
        require_access_shop(request.user, shop_id)
        groups = ClientGroup.objects.filter(shop_id=shop_id).prefetch_related("clients")
        return success_response(
            details="Groups retrieved", code="GROUPS_RETRIEVED", data=[serialize_group(group) for group in groups]
        )

    def post(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)

        name = (request.data.get("name") or "").strip()
        clients = get_clients(request.data.get("clients") or [])
        if not name:
            return error_response(details="Group name is required.", code="NAME_REQUIRED")
        if not clients.exists():
            return error_response(details="Select at least one client.", code="NO_CLIENTS")
        if ClientGroup.objects.filter(shop=shop, name__iexact=name).exists():
            return error_response(details="A group with this name already exists.", code="GROUP_NAME_EXISTS")

        group = ClientGroup.objects.create(shop=shop, name=name)
        group.clients.set(clients)
        return success_response(
            details="Group created", code="GROUP_SAVED", data=serialize_group_detail(request, group)
        )


class ClientGroupDetailAPIView(APIView):
    """GET: Group and its members. PATCH: Rename or change members. DELETE: Remove the group."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, pk, *args, **kwargs):
        require_access_shop(request.user, shop_id)
        group = get_object_or_404(ClientGroup, pk=pk, shop_id=shop_id)
        return success_response(
            details="Group retrieved", code="GROUP_RETRIEVED", data=serialize_group_detail(request, group)
        )

    def patch(self, request, shop_id, pk, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        group = get_object_or_404(ClientGroup, pk=pk, shop_id=shop_id)

        if "name" in request.data:
            name = (request.data.get("name") or "").strip()
            if not name:
                return error_response(details="Group name is required.", code="NAME_REQUIRED")
            duplicates = ClientGroup.objects.filter(shop_id=shop_id, name__iexact=name).exclude(pk=group.pk)
            if duplicates.exists():
                return error_response(details="A group with this name already exists.", code="GROUP_NAME_EXISTS")
            group.name = name
            group.save(update_fields=["name", "updated_at"])

        if "clients" in request.data:
            clients = get_clients(request.data.get("clients") or [])
            if not clients.exists():
                return error_response(details="A group needs at least one client.", code="NO_CLIENTS")
            group.clients.set(clients)

        return success_response(
            details="Group updated", code="GROUP_SAVED", data=serialize_group_detail(request, group)
        )

    def delete(self, request, shop_id, pk, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        get_object_or_404(ClientGroup, pk=pk, shop_id=shop_id).delete()
        return success_response(details="Group deleted", code="GROUP_DELETED", data={})


class ClientGroupMessagesAPIView(APIView):
    """GET: Group history for the shop's staff. POST: Admins and managers send to the group."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, pk, *args, **kwargs):
        require_access_shop(request.user, shop_id)
        group = get_object_or_404(ClientGroup, pk=pk, shop_id=shop_id)
        return success_response(
            details="Messages retrieved",
            code="MESSAGES_RETRIEVED",
            data={
                "group": serialize_group(group),
                "can_send": can_manage_shop(request.user, shop_id),
                "messages": serialize_thread(group.messages.all()),
            },
        )

    def post(self, request, shop_id, pk, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        group = get_object_or_404(ClientGroup.objects.select_related("shop"), pk=pk, shop_id=shop_id)
        body = get_message_body(request)
        if not body:
            return error_response(details="Message cannot be empty.", code="EMPTY_MESSAGE")

        message = ClientMessage.objects.create(shop=group.shop, sender=request.user, group=group, body=body)
        notify_clients(group.shop, group.clients.all(), body)
        return success_response(details="Message sent", code="MESSAGE_SENT", data=serialize_message(message))


class ClientDirectMessagesAPIView(APIView):
    """GET: A shop's history with one client. POST: Admins and managers message that client."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, client_id, *args, **kwargs):
        require_access_shop(request.user, shop_id)
        client = get_object_or_404(User, pk=client_id, role=UserRole.USER)
        messages = ClientMessage.objects.filter(shop_id=shop_id, recipient=client)
        return success_response(
            details="Messages retrieved",
            code="MESSAGES_RETRIEVED",
            data={
                "client": serialize_member(request, client),
                "can_send": can_manage_shop(request.user, shop_id),
                "messages": serialize_thread(messages),
            },
        )

    def post(self, request, shop_id, client_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)
        client = get_object_or_404(User, pk=client_id, role=UserRole.USER)
        body = get_message_body(request)
        if not body:
            return error_response(details="Message cannot be empty.", code="EMPTY_MESSAGE")

        message = ClientMessage.objects.create(shop=shop, sender=request.user, recipient=client, body=body)
        notify_clients(shop, [client], body)
        return success_response(details="Message sent", code="MESSAGE_SENT", data=serialize_message(message))


class MyMessagesAPIView(APIView):
    """GET: A customer's conversations: their groups plus each shop that messaged them directly."""

    permission_classes = [IsActiveUser]

    def get(self, request, *args, **kwargs):
        conversations = []
        for group in request.user.client_groups.select_related("shop"):
            last_message = group.messages.order_by("-created_at").first()
            conversations.append(
                {
                    "type": "group",
                    "id": group.id,
                    "name": group.name,
                    "shop": {"id": group.shop_id, "name": group.shop.name},
                    "last_message": serialize_message(last_message) if last_message else None,
                }
            )

        received = request.user.received_client_messages
        for shop_id in received.order_by().values_list("shop_id", flat=True).distinct():
            last_message = received.filter(shop_id=shop_id).select_related("shop").order_by("-created_at").first()
            conversations.append(
                {
                    "type": "direct",
                    "id": shop_id,
                    "name": last_message.shop.name,
                    "shop": {"id": shop_id, "name": last_message.shop.name},
                    "last_message": serialize_message(last_message),
                }
            )

        conversations.sort(
            key=lambda item: item["last_message"]["created_at"].isoformat() if item["last_message"] else "",
            reverse=True,
        )
        return success_response(details="Conversations retrieved", code="CONVERSATIONS_RETRIEVED", data=conversations)


class MyGroupMessagesAPIView(APIView):
    """GET: Group history for a customer who belongs to the group."""

    permission_classes = [IsActiveUser]

    def get(self, request, pk, *args, **kwargs):
        group = get_object_or_404(ClientGroup, pk=pk)
        if not group.clients.filter(pk=request.user.pk).exists() and not can_access_shop(request.user, group.shop_id):
            raise PermissionDenied("You are not a member of this group.")
        return success_response(
            details="Messages retrieved",
            code="MESSAGES_RETRIEVED",
            data={
                "group": {"id": group.id, "name": group.name},
                "can_send": False,
                "messages": serialize_thread(group.messages.all()),
            },
        )


class MyDirectMessagesAPIView(APIView):
    """GET: Messages a shop sent to the signed-in customer."""

    permission_classes = [IsActiveUser]

    def get(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        messages = ClientMessage.objects.filter(shop=shop, recipient=request.user)
        return success_response(
            details="Messages retrieved",
            code="MESSAGES_RETRIEVED",
            data={"can_send": False, "messages": serialize_thread(messages), "shop": {"id": shop.id, "name": shop.name}},
        )
