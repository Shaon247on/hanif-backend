import csv
import hashlib
import hmac
import json
import time
from datetime import timedelta

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.booking.models import Booking
from apps.core.access import require_access_shop, require_manage_shop, scope_to_user_shops
from apps.core.permissions import IsAdmin
from apps.core.responses import success_response
from config import env as env_module

from .models import PaymentLog
from .serializers import PaymentLogSerializer

STRIPE_SIGNATURE_TOLERANCE_SECONDS = 300


def is_valid_stripe_signature(payload: bytes, signature_header: str, secret: str) -> bool:
    """Verify a Stripe-Signature header as described in Stripe's webhook docs."""
    if not secret or not signature_header:
        return False

    timestamp = None
    signatures = []
    for item in signature_header.split(","):
        key, _, value = item.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)

    if not timestamp or not signatures:
        return False
    try:
        if abs(time.time() - int(timestamp)) > STRIPE_SIGNATURE_TOLERANCE_SECONDS:
            return False
    except ValueError:
        return False

    expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, signature) for signature in signatures)


class RevenueCatWebhookAPIView(APIView):
    """
    POST: Webhook endpoint for RevenueCat (Apple/Google Pay).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        secret = env_module.REVENUECAT_WEBHOOK_SECRET
        provided = request.headers.get("Authorization", "")
        if not secret or not hmac.compare_digest(provided, f"Bearer {secret}"):
            raise PermissionDenied("Invalid webhook credentials.")

        payload = request.data
        event = payload.get("event", {})

        # We assume `app_user_id` contains the booking_code or booking_id
        # In a real app, RevenueCat associates transactions with app_user_id
        app_user_id = event.get("app_user_id")
        transaction_id = event.get("transaction_id")
        price = event.get("price", 0.0)
        store = event.get("store")  # 'app_store' or 'play_store'

        method = "apple_pay" if store == "app_store" else "google_pay" if store == "play_store" else "other"

        # Try to find the booking
        booking = Booking.objects.filter(booking_code=app_user_id).first()
        if not booking and app_user_id and app_user_id.isdigit():
            booking = Booking.objects.filter(id=app_user_id).first()

        if booking:
            # Update booking status
            was_pending = booking.payment_status == "pending"
            booking.payment_status = "paid"
            booking.save()

            # Send notification if it was pending
            if was_pending:
                from apps.notification.utils import send_push_and_email

                send_push_and_email(
                    user=booking.customer,
                    title="Payment Received",
                    message=f"We have received your payment of ${booking.total_amount} for booking {booking.booking_code}.",
                    notif_type="system",
                    send_email=True,
                )

        # Create Payment Log
        PaymentLog.objects.create(
            booking=booking,
            amount=price,
            method=method,
            transaction_id=transaction_id,
            status="completed",
            raw_data=payload,
        )

        return success_response(details="Webhook received.", code="WEBHOOK_RECEIVED", data={})


class ManualPaymentLogAPIView(APIView):
    """
    POST: Log manual payments (cash/offline).
    GET: List all payment logs.
    """

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        # Admin checking all logs
        shop_id = request.query_params.get("shop")
        if shop_id:
            try:
                shop_id = int(shop_id)
            except (TypeError, ValueError):
                return success_response(
                    details="shop must be a valid integer.",
                    code="INVALID_SHOP_ID",
                    data={},
                    status_code=400,
                )
            require_access_shop(request.user, shop_id)
        duration_type = request.query_params.get("duration_type")  # e.g., 'daily', 'weekly', 'monthly'
        if duration_type:
            now = timezone.now()
            if duration_type == "daily":
                start_date = now - timedelta(days=1)
            elif duration_type == "weekly":
                start_date = now - timedelta(weeks=1)
            elif duration_type == "monthly":
                start_date = now - timedelta(days=30)
            elif duration_type == "yearly":
                start_date = now - timedelta(days=365)
            else:
                start_date = None

            if start_date:
                logs = PaymentLog.objects.filter(created_at__gte=start_date, booking__shop_id=shop_id) if shop_id else PaymentLog.objects.filter(created_at__gte=start_date)
            else:
                logs = PaymentLog.objects.filter(booking__shop_id=shop_id) if shop_id else PaymentLog.objects.all()
        else:
            logs = PaymentLog.objects.filter(booking__shop_id=shop_id) if shop_id else PaymentLog.objects.all()

        logs = scope_to_user_shops(logs, request.user, "booking__shop_id")
        logs = logs.select_related("booking")
        total_revenue = sum(log.amount for log in logs)
        appointment_count = logs.count()
        total_tips = sum({log.booking_id: log.booking.tip_amount for log in logs if log.booking}.values())
        serializer = PaymentLogSerializer(logs, many=True)
        data = {
            "total_revenue": total_revenue,
            "total_tips": total_tips,
            "cash_total": sum(log.amount for log in logs if log.method == "cash"),
            "card_total": sum(log.amount for log in logs if log.method == "card"),
            "appointment_count": appointment_count,
            "logs": serializer.data,
        }
        return success_response(details="Logs retrieved.", code="LOGS_RETRIEVED", data=data)

    def post(self, request, *args, **kwargs):
        booking_id = request.data.get("booking_id")
        amount = request.data.get("amount")
        method = request.data.get("method", "cash")

        booking = get_object_or_404(Booking, id=booking_id)
        require_manage_shop(request.user, booking.shop_id)

        was_pending = booking.payment_status == "pending"
        booking.payment_status = "paid"
        booking.payment_method = method
        booking.save()

        log = PaymentLog.objects.create(
            booking=booking, amount=amount or booking.total_amount, method=method, status="completed"
        )

        if was_pending:
            from apps.notification.utils import send_push_and_email

            send_push_and_email(
                user=booking.customer,
                title="Payment Received",
                message=f"We have received your manual payment for booking {booking.booking_code}.",
                notif_type="system",
                send_email=True,
            )

        return success_response(
            details="Manual payment logged.", code="MANUAL_PAYMENT_LOGGED", data=PaymentLogSerializer(log).data
        )


class PaymentLogDetailAPIView(APIView):
    """
    GET: Retrieve a single payment log.
    PUT/PATCH: Update a single payment log.
    DELETE: Delete a single payment log.
    """

    permission_classes = [IsAdmin]

    def get_object(self, pk):
        logs = scope_to_user_shops(PaymentLog.objects.all(), self.request.user, "booking__shop_id")
        return get_object_or_404(logs, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        log = self.get_object(pk)
        serializer = PaymentLogSerializer(log)
        return success_response(details="Payment log retrieved.", code="LOG_RETRIEVED", data=serializer.data)

    def patch(self, request, pk, *args, **kwargs):
        log = self.get_object(pk)
        serializer = PaymentLogSerializer(log, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(details="Payment log updated.", code="LOG_UPDATED", data=serializer.data)

    def delete(self, request, pk, *args, **kwargs):
        log = self.get_object(pk)
        log.delete()
        return success_response(details="Payment log deleted.", code="LOG_DELETED", data={})


class PaymentLogExportAPIView(APIView):
    """
    GET: Export payment logs as CSV for download.
    """

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        logs = scope_to_user_shops(PaymentLog.objects.all(), request.user, "booking__shop_id").select_related("booking")
        shop_id = request.query_params.get("shop")
        if shop_id:
            require_access_shop(request.user, shop_id)
            logs = logs.filter(booking__shop_id=shop_id)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="payment_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(["ID", "Booking Code", "Source", "Amount", "Tip", "Method", "Transaction ID", "Status", "Date"])

        for log in logs:
            b_code = log.booking.booking_code if log.booking else "N/A"
            writer.writerow(
                [
                    log.id,
                    b_code,
                    log.booking.get_source_display() if log.booking else "",
                    log.amount,
                    log.booking.tip_amount if log.booking else "",
                    log.method,
                    log.transaction_id or "",
                    log.status,
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                ]
            )

        return response

class StripeWebhookAPIView(APIView):
    """
    Handles Stripe Webhook events.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        payload = request.body

        signature = request.headers.get("Stripe-Signature", "")
        if not is_valid_stripe_signature(payload, signature, env_module.STRIPE_WEBHOOK_SECRET):
            return Response({"error": "Invalid signature"}, status=400)

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return Response({"error": "Invalid payload"}, status=400)

        if event.get("type") == "checkout.session.completed":
            session = event.get("data", {}).get("object", {})

            # Try to get booking code from client_reference_id or metadata
            booking_code = session.get("client_reference_id")
            if not booking_code:
                booking_code = session.get("metadata", {}).get("booking_code")

            if booking_code:
                try:
                    booking = Booking.objects.get(booking_code=booking_code)

                    # 1. Update Booking status and payment status
                    booking.payment_status = "paid"
                    booking.status = "confirmed"
                    booking.payment_method = "card"
                    booking.save()

                    # 2. Create PaymentLog
                    amount_total = session.get("amount_total")
                    amount = amount_total / 100 if amount_total else booking.total_amount

                    PaymentLog.objects.create(
                        booking=booking,
                        amount=amount,
                        method="card",
                        transaction_id=session.get("payment_intent") or session.get("id"),
                        status="completed",
                        raw_data=event
                    )
                except Booking.DoesNotExist:
                    pass

        return Response({"status": "success"}, status=200)
