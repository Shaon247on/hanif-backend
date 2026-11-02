import datetime
import os
import urllib.parse
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.booking.services import checkout_booking, create_walk_in_order
from apps.core.access import can_access_shop, can_manage_shop, require_access_shop
from apps.core.permissions import IsShopStaff
from apps.core.responses import success_response
from apps.barber.models import Barber
from apps.notification.utils import send_push_and_email
from apps.schedule.services import ScheduleService
from apps.service.models import Service
from apps.shop.models import Shop
from apps.user.models import User
from apps.user.services import get_or_create_customer

from .models import Appointment, Booking, ShopReview
from .serializers import (
    BookingCheckoutSerializer,
    BookingCreateSerializer,
    BookingDetailsSerializer,
    BookingSerializer,
    ShopReviewSerializer,
    WalkInOrderSerializer,
)

# Payment, status and pricing fields stay with the shop's own staff.
CUSTOMER_EDITABLE_BOOKING_FIELDS = {"barber", "services", "appointment_date", "start_time"}


def get_booking_for_user(user, pk):
    """Return a booking the user owns or that belongs to a shop they work in."""
    booking = get_object_or_404(Booking, pk=pk)
    if booking.customer_id != user.id and not can_access_shop(user, booking.shop_id):
        raise PermissionDenied("You do not have access to this booking.")
    return booking


class BookingCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        serializer = BookingCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()
        payment_url = None

        is_created_by_staff = can_access_shop(request.user, booking.shop_id)

        if not is_created_by_staff and booking.shop.payment_gateway_enabled:
            payment_url = self._create_stripe_checkout_session(booking)

        elif booking.payment_method:
            # A reservation is paid for at the shop, so payment is recorded at checkout.
            booking.status = "confirmed"
            booking.save(update_fields=["status"])
        else:
            # If no payment method is provided, the booking stays in "pending" status and "pending" payment_status
            pass

        # Send Notification and Email
        shop_name = booking.shop.name if booking.shop else "our shop"
        send_push_and_email(
            user=booking.customer,
            title=f"Booking Confirmed at {shop_name}",
            message=f"Your booking (Code: {booking.booking_code}) has been successfully created. Thank you for choosing {shop_name}!",
            notif_type="booking",
            send_email=True,
        )

        return success_response(
            details="Booking created successfully.",
            code="BOOKING_CREATED",
            data={**BookingSerializer(booking, context={"request": request}).data, "payment_url": payment_url},
        )

    def _create_stripe_checkout_session(self, booking):
        secret_key = os.environ.get("STRIPE_SECRET_KEY")
        if not secret_key:
            return None
        amount_cents = int((Decimal(str(booking.total_amount)) * 100).quantize(Decimal("1")))
        try:
            response = requests.post(
                "https://api.stripe.com/v1/checkout/sessions",
                auth=(secret_key, ""),
                data={
                    "mode": "payment",
                    "success_url": os.environ.get("STRIPE_SUCCESS_URL", "http://localhost:3000/payment/success"),
                    "cancel_url": os.environ.get("STRIPE_CANCEL_URL", "http://localhost:3000/payment/cancel"),
                    "client_reference_id": booking.booking_code,
                    "customer_email": booking.customer.email,
                    "line_items[0][price_data][currency]": os.environ.get("STRIPE_CURRENCY", "usd"),
                    "line_items[0][price_data][product_data][name]": f"BarberBay booking {booking.booking_code}",
                    "line_items[0][price_data][unit_amount]": amount_cents,
                    "line_items[0][quantity]": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json().get("url")
        except requests.RequestException:
            return None


class WalkInOrderAPIView(APIView):
    """POST: Admin, manager or barber records an order for a customer in the shop."""

    permission_classes = [IsShopStaff]

    def post(self, request, *args, **kwargs):
        serializer = WalkInOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            customer, is_new_customer = data.get("customer_id"), False
            if not customer:
                details = data["customer"]
                customer, is_new_customer = get_or_create_customer(
                    details["email"], details["full_name"], details["phone"]
                )
            booking = create_walk_in_order(
                customer=customer,
                shop=data["shop"],
                barber=data["barber"],
                services=data["services"],
                start_time=data.get("start_time"),
                payment_method=data["payment_method"],
                is_paid=data["is_paid"],
                tip_amount=data["tip_amount"],
                discount=data["discount"],
            )

        message = (
            f"Your order {booking.booking_code} at {booking.shop.name} has been created. "
            "Log in to the app to see it."
        )
        if is_new_customer:
            message += " Use Forgot password with this email to set your password."
        send_push_and_email(
            user=customer,
            title=f"Your order at {booking.shop.name}",
            message=message,
            notif_type="booking",
            send_email=True,
        )

        return success_response(
            details="Walk-in order created.",
            code="WALK_IN_ORDER_CREATED",
            data=BookingDetailsSerializer(booking, context={"request": request}).data,
        )


class BookingCheckoutAPIView(APIView):
    """POST: Take cash or card at the shop, record tip and discount, and complete the order."""

    permission_classes = [IsShopStaff]

    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk)
        require_access_shop(request.user, booking.shop_id)

        serializer = BookingCheckoutSerializer(data=request.data, context={"booking": booking, "request": request})
        serializer.is_valid(raise_exception=True)
        was_unpaid = booking.payment_status != "paid"
        booking = checkout_booking(booking, **serializer.validated_data)

        if was_unpaid:
            send_push_and_email(
                user=booking.customer,
                title="Payment Received",
                message=f"We have received your payment of ${booking.total_amount} for order {booking.booking_code}.",
                notif_type="system",
                send_email=True,
            )

        return success_response(
            details="Order completed.",
            code="BOOKING_CHECKED_OUT",
            data=BookingDetailsSerializer(booking, context={"request": request}).data,
        )


class BookingListAPIView(APIView):
    """GET: List upcoming or past bookings (type=upcoming|past)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        view_type = request.query_params.get("view_type", "user")
        booking_type = request.query_params.get("type", "upcoming")
        display_mode = request.query_params.get("display_mode", "list")  # 'list' or 'calendar'
        today = timezone.localdate()

        if view_type in ["admin", "staff"]:
            shop_id = request.query_params.get("shop_id")
            date_str = request.query_params.get("date")

            if not shop_id:
                return success_response(details="Shop ID is required.", code="MISSING_SHOP_ID", data={}, status_code=400)

            require_access_shop(request.user, shop_id)

            target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
            
            # Fetch bookings for the specific shop and date
            bookings = Booking.objects.filter(
                shop_id=shop_id, 
                appointments__appointment_date=target_date
            ).exclude(status="cancelled").distinct()
            
            if display_mode == "calendar":
                # For calendar view: group by barber
                barbers_data = {}
                shop_barbers = Barber.objects.filter(shop_id=shop_id).select_related("user")
                weekday = target_date.strftime("%A").lower()
                shop = Shop.objects.get(pk=shop_id)
                hours = ScheduleService.get_shop_hours(shop, target_date)
                for barber in shop_barbers:
                    schedule = ScheduleService.get_barber_schedule(barber, target_date, hours)
                    shift = schedule["override"] or schedule["recurring_shift"]
                    shifts = (
                        [
                            {
                                "id": shift.id,
                                "day_of_week": target_date.strftime("%A").lower(),
                                "shift_date": target_date,
                                "start_time": schedule["start_time"],
                                "end_time": schedule["end_time"],
                            }
                        ]
                        if schedule["is_working"]
                        else []
                    )
                    image = request.build_absolute_uri(barber.user.image.url) if barber.user.image else None
                    barbers_data[barber.id] = {
                        "barber": {
                            "id": barber.id,
                            "name": barber.user.full_name or barber.user.username,
                            "image": image,
                            "avatar": image,
                        },
                        "shifts": shifts,
                        "breaks": [
                            {
                                "id": item.id,
                                "day_of_week": item.day_of_week,
                                "break_date": item.break_date,
                                "start_time": item.start_time,
                                "end_time": item.end_time,
                                "title": item.title,
                            }
                            for item in schedule["breaks"]
                        ],
                        "time_off": [
                            {
                                "id": item.id,
                                "start_date": item.start_date,
                                "end_date": item.end_date,
                                "is_full_day": item.is_full_day,
                                "start_time": item.start_time,
                                "end_time": item.end_time,
                                "reason": item.reason,
                                "status": item.status,
                            }
                            for item in schedule["time_off"]
                        ],
                        "appointments": [],
                    }
                for booking in bookings:
                    for appt in Appointment.objects.filter(booking=booking, appointment_date=target_date):
                        barber_id = appt.barber.id if appt.barber else "unassigned"
                        if barber_id not in barbers_data:
                            barbers_data[barber_id] = {
                                "barber": {
                                    "id": appt.barber.id if appt.barber else None,
                                    "name": appt.barber.user.full_name if appt.barber and appt.barber.user else "Unassigned",
                                    "image": request.build_absolute_uri(appt.barber.user.image.url) if appt.barber and appt.barber.user and appt.barber.user.image else None,
                                    "avatar": request.build_absolute_uri(appt.barber.user.image.url) if appt.barber and appt.barber.user and appt.barber.user.image else None,
                                },
                                "shifts": [],
                                "breaks": [],
                                "time_off": [],
                                "appointments": []
                            }
                        
                        barbers_data[barber_id]["appointments"].append({
                            "booking_id": booking.id,
                            "appointment_id": appt.id,
                            "customer_name": booking.customer.full_name or booking.customer.username,
                            "service_name": appt.service.name,
                            "start_time": appt.start_time.strftime("%H:%M"),
                            "end_time": appt.end_time.strftime("%H:%M"),
                            "status": appt.status
                        })
                
                business_hours = {
                    "source": hours["source"],
                    "open_time": hours["open_time"],
                    "close_time": hours["close_time"],
                    "is_closed": hours["is_closed"],
                    "closure_reason": hours["closure_reason"],
                    "time_off": {
                        "is_off": hours["is_closed"],
                        "start_time": hours["open_time"],
                        "end_time": hours["close_time"],
                    },
                    # Partial closures block the same grid time as a break
                    "breaks": hours["breaks"]
                    + [{**item, "id": f"closure-{item['id']}"} for item in hours["closures"]],
                }
                data = {
                    "date": target_date,
                    "shop": {"id": shop_id, "name": shop.name},
                    "business_hours": business_hours,
                    "barbers": list(barbers_data.values()),
                }
                return success_response(details="Calendar view data retrieved.", code="CALENDAR_VIEW", data=data)
                
            else:
                # For list view: return grouped date dictionary for target_date - 4 days to target_date + 2 days
                from datetime import timedelta
                from apps.booking.serializers import BookingListViewSerializer

                start_range = target_date - timedelta(days=4)
                end_range = target_date + timedelta(days=2)

                # Fetch bookings in this range
                range_bookings = Booking.objects.filter(
                    shop_id=shop_id,
                    appointments__appointment_date__range=(start_range, end_range)
                ).exclude(status="cancelled").prefetch_related("appointments", "appointments__service", "appointments__barber", "customer").distinct()

                result_data = []
                list_shop = get_object_or_404(Shop, pk=shop_id)
                current_day = start_range
                while current_day <= end_range:
                    # day name string for the key, ex: Thu, 16 July
                    day_str = current_day.strftime("%a, %d %B")
                    day_hours = ScheduleService.get_shop_hours(list_shop, current_day)
                    shop_start_time = day_hours["open_time"]
                    shop_end_time = day_hours["close_time"]
                    is_closed = day_hours["is_closed"]
                    if is_closed:
                        current_day += timedelta(days=1)
                        continue  # Skip closed days

                    day_bookings = [
                        b for b in range_bookings
                        if any(appt.appointment_date == current_day for appt in b.appointments.all())
                    ]

                    total_value = sum(b.total_amount for b in day_bookings)
                    
                    client_ids = [b.customer_id for b in day_bookings]
                    new_client_count = User.objects.filter(id__in=client_ids, date_joined__date=current_day).count()

                    serialized_bookings = BookingListViewSerializer(day_bookings, many=True, context={"request": request}).data

                    result_data.append ({
                        "date": day_str,
                        "shop_start_time": shop_start_time,
                        "shop_end_time": shop_end_time,
                        "total_ammount": float(total_value),
                        "new_client_count": new_client_count,
                        "appointment_count": len(day_bookings),
                        "appointments": serialized_bookings,
                    })
                    current_day += timedelta(days=1)

                return success_response(
                    details="List view data retrieved.",
                    code="LIST_VIEW",
                    data=result_data
                )
                
        else:
            # User View
            bookings = Booking.objects.filter(customer=request.user)

            if booking_type == "upcoming":
                bookings = bookings.filter(
                    appointments__appointment_date__gte=today, status__in=["pending", "confirmed"]
                ).distinct()
            elif booking_type == "past":
                bookings = bookings.filter(
                    Q(appointments__appointment_date__lt=today) | Q(status__in=["completed", "cancelled", "refunded"])
                ).distinct()
            
            serializer = BookingSerializer(bookings, many=True)
            return success_response(details="Booking list retrieved.", code="BOOKING_LIST", data=serializer.data)




    
class BookingUpdateAPIView(APIView):
    """PUT/PATCH: Update a booking."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, *args, **kwargs):
        booking = get_booking_for_user(request.user, pk)
        return success_response(
            details="Booking details retrieved successfully.",
            code="BOOKING_DETAILS_RETRIEVED",
            data=BookingDetailsSerializer(booking, context={"request": request}).data,
        )

    def patch(self, request, pk, *args, **kwargs):
        booking = get_booking_for_user(request.user, pk)
        if not can_access_shop(request.user, booking.shop_id):
            if set(request.data) - CUSTOMER_EDITABLE_BOOKING_FIELDS:
                raise PermissionDenied("You can only change the barber, services, date or time.")

        serializer = BookingSerializer(booking, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(details="Booking updated successfully.", code="BOOKING_UPDATED", data=serializer.data)


class BookingCancelAPIView(APIView):
    """POST: Cancel a booking."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        booking = get_booking_for_user(request.user, pk)

        if booking.status in ["cancelled", "completed", "refunded"]:
            return success_response(details="Booking cannot be cancelled.", code="INVALID_STATUS", data={})

        booking.status = "cancelled"
        booking.save()

        appointments = Appointment.objects.filter(booking=booking)
        if appointments:
            appointments.update(status="cancelled")

        # Send Cancellation Notification (No Email required per instructions)
        send_push_and_email(
            user=booking.customer,
            title="Booking Cancelled",
            message=f"Your booking {booking.booking_code} has been cancelled successfully.",
            notif_type="booking",
            send_email=False,
        )

        return success_response(
            details="Booking cancelled successfully.", code="BOOKING_CANCELLED", data=BookingSerializer(booking).data
        )


class BookingGoogleCalendarSyncAPIView(APIView):
    """
    POST: Create event in Google Calendar
    PUT: Update event in Google Calendar
    DELETE: Delete event from Google Calendar
    GET: Get event details from Google Calendar
    """
    permission_classes = [IsAuthenticated]

    def _get_event_data(self, booking):
        appointments = list(Appointment.objects.filter(booking=booking).order_by("appointment_date", "start_time"))
        if not appointments:
            return None

        first_appt = appointments[0]
        last_appt = appointments[-1]

        start_datetime = timezone.make_aware(datetime.datetime.combine(first_appt.appointment_date, first_appt.start_time))
        end_datetime = timezone.make_aware(datetime.datetime.combine(last_appt.appointment_date, last_appt.end_time))

        return {
            "summary": f"Appointment at {booking.shop.name}",
            "description": f"Booking Code: {booking.booking_code}\nServices: " + ", ".join(app.service.name for app in appointments),
            "location": booking.shop.location,
            "start": {
                "dateTime": start_datetime.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_datetime.isoformat(),
                "timeZone": "UTC",
            }
        }

    def post(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, customer=request.user)
        access_token = request.data.get("access_token")
        
        if not access_token:
            return success_response(details="Google access_token is required.", code="MISSING_TOKEN", data={}, status_code=400)
            
        event_data = self._get_event_data(booking)
        if not event_data:
            return success_response(details="No appointments found.", code="NO_APPOINTMENTS", data={}, status_code=400)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        res = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            json=event_data,
            headers=headers
        )
        
        if res.status_code in [200, 201]:
            data = res.json()
            booking.google_event_id = data.get("id")
            booking.save(update_fields=['google_event_id'])
            return success_response(details="Event created in Google Calendar.", code="EVENT_CREATED", data=data)
            
        return success_response(details="Failed to create event.", code="API_ERROR", data=res.json(), status_code=res.status_code)

    def put(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, customer=request.user)
        access_token = request.data.get("access_token")
        
        if not access_token:
            return success_response(details="Google access_token is required.", code="MISSING_TOKEN", data={}, status_code=400)
            
        if not booking.google_event_id:
            return success_response(details="Booking is not synced with Google Calendar yet.", code="NOT_SYNCED", data={}, status_code=400)
            
        event_data = self._get_event_data(booking)
        if not event_data:
            return success_response(details="No appointments found.", code="NO_APPOINTMENTS", data={}, status_code=400)

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        res = requests.put(
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{booking.google_event_id}",
            json=event_data,
            headers=headers
        )
        
        if res.status_code == 200:
            return success_response(details="Event updated in Google Calendar.", code="EVENT_UPDATED", data=res.json())
            
        return success_response(details="Failed to update event.", code="API_ERROR", data=res.json(), status_code=res.status_code)

    def get(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, customer=request.user)
        access_token = request.query_params.get("access_token")
        
        if not access_token:
            return success_response(details="Google access_token is required.", code="MISSING_TOKEN", data={}, status_code=400)
            
        if not booking.google_event_id:
            return success_response(details="Booking is not synced with Google Calendar yet.", code="NOT_SYNCED", data={}, status_code=400)

        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        res = requests.get(
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{booking.google_event_id}",
            headers=headers
        )
        
        if res.status_code == 200:
            return success_response(details="Event retrieved from Google Calendar.", code="EVENT_RETRIEVED", data=res.json())
            
        return success_response(details="Failed to get event.", code="API_ERROR", data=res.json(), status_code=res.status_code)

    def delete(self, request, pk, *args, **kwargs):
        booking = get_object_or_404(Booking, pk=pk, customer=request.user)
        access_token = request.data.get("access_token")
        
        if not access_token:
            return success_response(details="Google access_token is required.", code="MISSING_TOKEN", data={}, status_code=400)
            
        if not booking.google_event_id:
            return success_response(details="Booking is not synced with Google Calendar yet.", code="NOT_SYNCED", data={}, status_code=400)

        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        res = requests.delete(
            f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{booking.google_event_id}",
            headers=headers
        )
        
        if res.status_code == 204:
            booking.google_event_id = None
            booking.save(update_fields=['google_event_id'])
            return success_response(details="Event deleted from Google Calendar.", code="EVENT_DELETED", data={})
            
        return success_response(details="Failed to delete event.", code="API_ERROR", data={"details": res.text}, status_code=res.status_code)


class BarberAvailabilityAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        barber_id = request.query_params.get("barber_id")
        date_str = request.query_params.get("date")
        service_ids = request.query_params.get("services", "")

        from apps.core.responses import error_response

        if not barber_id or not date_str or not service_ids:
            return error_response(details="Missing required parameters", code="MISSING_PARAMS", data=[])

        target_date = parse_date(date_str)
        if not target_date:
            return error_response(details="Invalid date format", code="INVALID_DATE", data=[])

        service_ids = [int(sid) for sid in service_ids.split(",") if sid.isdigit()]
        services = Service.objects.filter(id__in=service_ids)
        total_duration = sum(service.duration_minutes for service in services)
        if total_duration == 0:
            return error_response(details="Invalid services", code="INVALID_SERVICES", data=[])

        day_of_week = target_date.strftime("%A").lower()

        # Support both UUID (User ID) and Integer (Barber ID)
        import uuid
        is_uuid = False
        try:
            uuid.UUID(str(barber_id))
            is_uuid = True
        except ValueError:
            pass

        if is_uuid:
            barber_obj = Barber.objects.filter(user_id=barber_id).select_related("shop").first()
        elif str(barber_id).isdigit():
            barber_obj = Barber.objects.filter(id=barber_id).select_related("shop").first()
        else:
            return error_response(details="Invalid barber ID format", code="INVALID_BARBER", data=[])

        if not barber_obj:
            return error_response(details="Barber not found", code="BARBER_NOT_FOUND", data=[])

        available_slots = ScheduleService.get_available_slots(barber_obj, target_date, total_duration)

        if not available_slots:
            return success_response(details="No slots available", code="NO_SLOTS", data=[])

        return success_response(details="Available slots retrieved.", code="AVAILABLE_SLOTS", data=available_slots)


class ShopReviewListCreateAPIView(APIView):
    """
    GET: List all reviews (optionally filter by shop).
    POST: Create a new review.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop")
        barber_id = request.query_params.get("barber")
        if shop_id:
            reviews = ShopReview.objects.filter(shop_id=shop_id)
        elif barber_id:
            reviews = ShopReview.objects.filter(booking__appointments__barber_id=barber_id).distinct()
        else:
            reviews = ShopReview.objects.all()
        serializer = ShopReviewSerializer(reviews, many=True, context={"request": request})

        if shop_id:
            google_reviews = []
            rating = 0.0
            total_ratings = 0
            google_review_link = None

            try:
                shop = Shop.objects.get(pk=shop_id)
                google_review_link = shop.google_review_link
                if shop.google_place_id:
                    api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY"))
                    if api_key:
                        url = "https://maps.googleapis.com/maps/api/place/details/json"
                        params = {
                            "place_id": shop.google_place_id,
                            "fields": "rating,user_ratings_total,reviews",
                            "key": api_key,
                            "language": "en",
                        }
                        res = requests.get(url, params=params, timeout=5)
                        if res.status_code == 200:
                            res_data = res.json()
                            if res_data.get("status") == "OK":
                                result = res_data.get("result", {})
                                rating = result.get("rating", 0.0)
                                total_ratings = result.get("user_ratings_total", 0)
                                google_reviews = result.get("reviews", [])
            except Exception:
                pass

            return success_response(
                details="Shop reviews retrieved successfully.",
                code="SHOP_REVIEW_LIST_RETRIEVED",
                data={
                    "local_reviews": serializer.data,
                    "google_review_link": google_review_link,
                    "google_rating": rating,
                    "google_total_ratings": total_ratings,
                    "google_reviews": google_reviews,
                },
            )

        return success_response(
            details="Shop reviews retrieved successfully.",
            code="SHOP_REVIEW_LIST_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
        serializer = ShopReviewSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            details="Shop review created successfully.",
            code="SHOP_REVIEW_CREATED",
            data=serializer.data,
        )


class ShopReviewDetailsUpdateDeleteAPIView(APIView):
    """
    GET: Retrieve review details.
    PUT/PATCH: Update review details.
    DELETE: Delete a review.
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(ShopReview, pk=pk)

    def get_editable_object(self, request, pk):
        review = self.get_object(pk)
        if review.customer_id != request.user.id and not can_manage_shop(request.user, review.shop_id):
            raise PermissionDenied("You can only change your own reviews.")
        return review

    def get(self, request, pk, *args, **kwargs):
        review = self.get_object(pk)
        serializer = ShopReviewSerializer(review)
        return success_response(
            details="Shop review details retrieved successfully.",
            code="SHOP_REVIEW_DETAILS_RETRIEVED",
            data=serializer.data,
        )

    def put(self, request, pk, *args, **kwargs):
        review = self.get_editable_object(request, pk)
        serializer = ShopReviewSerializer(review, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated_review = serializer.save()
        return success_response(
            details="Shop review updated successfully.",
            code="SHOP_REVIEW_UPDATED",
            data=ShopReviewSerializer(updated_review).data,
        )

    def delete(self, request, pk, *args, **kwargs):
        review = self.get_editable_object(request, pk)
        review.delete()
        return success_response(
            details="Shop review deleted successfully.",
            code="SHOP_REVIEW_DELETED",
            data={},
        )
