from django.db.models import Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from apps.booking.models import Booking
from apps.core.access import is_global_admin, require_access_shop
from apps.core.permissions import IsShopStaff
from apps.core.responses import success_response


class AdminDashboardAPIView(APIView):
    """GET: Get admin home dashboard data."""

    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop") or request.user.active_shop_id
        if shop_id:
            require_access_shop(request.user, shop_id)
        elif not is_global_admin(request.user):
            raise PermissionDenied("A shop is required.")
        today = timezone.localdate()

        # Base query for today's bookings
        bookings_today = Booking.objects.filter(appointments__appointment_date=today).distinct()

        if shop_id:
            bookings_today = bookings_today.filter(shop_id=shop_id)

        # Metrics
        total_bookings = bookings_today.count()
        completed_bookings = bookings_today.filter(status="completed").count()
        in_service_bookings = bookings_today.filter(status="in_progress").count()

        revenue_today = (
            bookings_today.filter(status__in=["completed", "paid"]).aggregate(total=Sum("total_amount"))["total"]
            or 0.00
        )

        # Upcoming Bookings
        upcoming_qs = (
            bookings_today.filter(
                appointments__start_time__gte=timezone.localtime().time(), status__in=["pending", "confirmed"]
            )
            .distinct()
            .order_by("appointments__start_time")
        )

        upcoming_bookings = []
        for booking in upcoming_qs:
            appts = booking.appointments.all()  # type: ignore
            if not appts:
                continue

            first_appt = appts.first()
            services_names = ", ".join([app.service.name for app in appts])
            total_duration = sum([app.service.duration_minutes for app in appts])

            customer_name = booking.customer.username
            if booking.customer.first_name:
                customer_name = f"{booking.customer.first_name} {booking.customer.last_name}".strip()

            upcoming_bookings.append(
                {
                    "id": booking.id,
                    "customer_name": customer_name,
                    "services": services_names,
                    "price": booking.total_amount,
                    "duration_minutes": total_duration,
                    "start_time": first_appt.start_time.strftime("%H:%M") if first_appt else "",
                }
            )

        data = {
            "metrics": {
                "todays_bookings": total_bookings,
                "completed": completed_bookings,
                "in_service": in_service_bookings,
                "revenue_today": float(revenue_today),
            },
            "upcoming_bookings": upcoming_bookings,
        }

        return success_response(details="Dashboard data retrieved", code="DASHBOARD_DATA", data=data)
