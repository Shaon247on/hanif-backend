from django.urls import path

from .views import (
    BarberAvailabilityAPIView,
    BookingCancelAPIView,
    BookingCheckoutAPIView,
    BookingCreateAPIView,
    BookingGoogleCalendarSyncAPIView,
    BookingListAPIView,
    BookingUpdateAPIView,
    ShopReviewDetailsUpdateDeleteAPIView,
    ShopReviewListCreateAPIView,
    WalkInOrderAPIView,
)

urlpatterns = [
    path("booking/", BookingListAPIView.as_view(), name="booking-list"),
    path("bookings/", BookingCreateAPIView.as_view(), name="booking-create-root"),
    path("bookings/create/", BookingCreateAPIView.as_view(), name="booking-create"),
    path("bookings/walk-in/", WalkInOrderAPIView.as_view(), name="booking-walk-in"),
    path("bookings/<int:pk>/", BookingUpdateAPIView.as_view(), name="booking-update"),
    path("bookings/<int:pk>/checkout/", BookingCheckoutAPIView.as_view(), name="booking-checkout"),
    path("bookings/<int:pk>/cancel/", BookingCancelAPIView.as_view(), name="booking-cancel"),
    path("bookings/<int:pk>/calendar/", BookingGoogleCalendarSyncAPIView.as_view(), name="booking-calendar"),
    path("bookings/available-slots/", BarberAvailabilityAPIView.as_view(), name="booking-available-slots"),
    path("bookings/reviews/", ShopReviewListCreateAPIView.as_view(), name="review-list-create"),
    path("bookings/reviews/<int:pk>/", ShopReviewDetailsUpdateDeleteAPIView.as_view(), name="review-detail-update-delete"),
]
