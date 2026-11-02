from django.urls import path

from .views import (
    BarberBreakDetailAPIView,
    BarberBreakListCreateAPIView,
    BarberShiftDetailAPIView,
    BarberShiftListCreateAPIView,
    BarberTimeOffDetailAPIView,
    BarberTimeOffListCreateAPIView,
    BarberTimeOffApprovalAPIView,
    BarberScheduleUpdateAPIView,
    BusinessHourAPIView,
    OpeningCalendarAPIView,
    BusinessOffAPIView,
)

urlpatterns = [
    # Business Hours (Shop Level)
    path("business-hours/<int:shop_id>/", BusinessHourAPIView.as_view(), name="business-hours"),
    path("opening-calendar/", OpeningCalendarAPIView.as_view(), name="opening-calendar"),
    path("business/off/", BusinessOffAPIView.as_view(), name="business-off-list-create"),
    path("business/off/<int:pk>/", BusinessOffAPIView.as_view(), name="business-off-detail-update-delete"),
    # Barber Shifts (Working Hours)
    path("shifts/", BarberShiftListCreateAPIView.as_view(), name="shift-list-create"),
    path("shifts/<int:pk>/", BarberShiftDetailAPIView.as_view(), name="shift-detail-update-delete"),
    # Barber Breaks
    path("breaks/", BarberBreakListCreateAPIView.as_view(), name="break-list-create"),
    path("breaks/<int:pk>/", BarberBreakDetailAPIView.as_view(), name="break-detail-update-delete"),
    # Barber Time Off
    path("time-off/", BarberTimeOffListCreateAPIView.as_view(), name="timeoff-list-create"),
    path("time-off/<int:pk>/", BarberTimeOffDetailAPIView.as_view(), name="timeoff-detail-update-delete"),
    path("time-off/<int:pk>/approval/", BarberTimeOffApprovalAPIView.as_view(), name="timeoff-approval"),
    path("barber-schedule/", BarberScheduleUpdateAPIView.as_view(), name="barber-schedule-update"),
    path("barber/schedule/", BarberScheduleUpdateAPIView.as_view(), name="barber-schedule-update-slash"),
    path("shifts/override/", BarberScheduleUpdateAPIView.as_view(), name="barber-shift-override"),
]

