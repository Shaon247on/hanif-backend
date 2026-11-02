from django.urls import path

from .views import (
    ManualPaymentLogAPIView,
    PaymentLogDetailAPIView,
    PaymentLogExportAPIView,
    RevenueCatWebhookAPIView,
    StripeWebhookAPIView,
)

urlpatterns = [
    # Webhook
    path("payments/webhook/revenuecat/", RevenueCatWebhookAPIView.as_view(), name="revenuecat-webhook"),
    path("payments/webhook/stripe/", StripeWebhookAPIView.as_view(), name="stripe-webhook"),
    # Manual payment logging & viewing (List)
    path("payments/manual/", ManualPaymentLogAPIView.as_view(), name="manual-payment-log"),
    # Edit / Delete single payment log
    path("payments/manual/<int:pk>/", PaymentLogDetailAPIView.as_view(), name="payment-log-detail"),
    # Export logs to CSV
    path("payments/export/", PaymentLogExportAPIView.as_view(), name="payment-log-export"),
]
