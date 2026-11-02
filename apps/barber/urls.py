"""Barber URL configuration."""

from django.urls import path

from .views import BarberDetailsUpdateDeleteAPIView, BarberListCreateAPIView, ShopBarberOptionsAPIView
from .profile_views import (
    StaffProfileAPIView,
    StaffServicesAPIView,
    StaffScheduleAPIView,
    StaffTimeOffAPIView,
    StaffReviewAPIView,
    StaffReportAPIView,
    StaffShopAPIView,
)

urlpatterns = [
    path("barbers/", BarberListCreateAPIView.as_view(), name="barber-list-create"),
    path("barbers/by-shop/", ShopBarberOptionsAPIView.as_view(), name="barber-options-by-shop"),
    path("barbers/<int:pk>/", BarberDetailsUpdateDeleteAPIView.as_view(), name="barber-detail-update-delete"),
    
    # Staff Profile specific APIs for logged-in barber
    path("barbers/me/profile/", StaffProfileAPIView.as_view(), name="staff-me-profile"),
    path("barbers/me/services/", StaffServicesAPIView.as_view(), name="staff-me-services"),
    path("barbers/me/schedule/", StaffScheduleAPIView.as_view(), name="staff-me-schedule"),
    path("barbers/me/time-off/", StaffTimeOffAPIView.as_view(), name="staff-me-time-off"),
    path("barbers/me/reviews/", StaffReviewAPIView.as_view(), name="staff-me-reviews"),
    path("barbers/me/reports/", StaffReportAPIView.as_view(), name="staff-me-reports"),
    path("barbers/me/shop/", StaffShopAPIView.as_view(), name="staff-me-shop"),
]
