"""Notification URL configuration."""

from django.urls import path

from .views import AdminSendNotificationAPIView, NotificationListAPIView

urlpatterns = [
    # General notification endpoints for the logged-in user
    path("notifications/", NotificationListAPIView.as_view(), name="notification-list"),
    # Admin push notification endpoint
    path("notifications/send/", AdminSendNotificationAPIView.as_view(), name="notification-send"),
]
