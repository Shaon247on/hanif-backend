from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.permissions import IsGlobalAdmin
from apps.core.responses import success_response
from apps.user.models import User

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListAPIView(APIView):
    """GET: List notifications for logged in user. POST: Mark as read."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        notifications = Notification.objects.filter(user=request.user)
        serializer = NotificationSerializer(notifications, many=True)

        unread_count = notifications.filter(is_read=False).count()
        data = {"unread_count": unread_count, "notifications": serializer.data}
        return success_response(details="Notifications retrieved.", code="NOTIFICATIONS_RETRIEVED", data=data)

    def post(self, request, *args, **kwargs):
        """Mark notification(s) as read."""
        notification_id = request.data.get("notification_id")

        if notification_id:
            notif = get_object_or_404(Notification, id=notification_id, user=request.user)
            notif.is_read = True
            notif.save()
            return success_response(details="Notification marked as read.", code="NOTIFICATION_READ", data={})
        else:
            # Mark all as read
            Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
            return success_response(details="All notifications marked as read.", code="ALL_NOTIFICATIONS_READ", data={})


class AdminSendNotificationAPIView(APIView):
    """POST: Admin can push notifications to specific roles or users."""

    permission_classes = [IsGlobalAdmin]

    def post(self, request, *args, **kwargs):
        title = request.data.get("title")
        message = request.data.get("message")
        role = request.data.get("role")  # e.g. 'user', 'barber', 'shop_admin'
        user_id = request.data.get("user_id")
        notif_type = request.data.get("type", "system")

        if not title or not message:
            return success_response(details="Title and message are required.", code="MISSING_FIELDS", data={})

        users = User.objects.none()

        if user_id:
            users = User.objects.filter(id=user_id)
        elif role:
            users = User.objects.filter(role=role)
        else:
            # Send to everyone
            users = User.objects.all()

        if not users.exists():
            return success_response(details="No target users found.", code="NO_USERS", data={})

        notifications_to_create = [Notification(user=u, title=title, message=message, type=notif_type) for u in users]

        Notification.objects.bulk_create(notifications_to_create)

        return success_response(
            details=f"Notification sent to {len(notifications_to_create)} users.", code="NOTIFICATION_SENT", data={}
        )
