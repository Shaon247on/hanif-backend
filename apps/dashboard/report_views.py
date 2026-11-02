"""Dashboard reporting endpoints."""

import datetime
from decimal import Decimal

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Sum
from rest_framework.views import APIView

from apps.booking.models import Appointment, Booking
from apps.core.access import require_manage_shop
from apps.core.permissions import IsAdmin
from apps.core.responses import success_response
from apps.shop.models import Shop


class AdminReportAPIView(APIView):
    """Return completed appointment metrics grouped by staff for one shop."""

    permission_classes = [IsAdmin]

    def get(self, request, *args, **kwargs):
        period = request.query_params.get("period", "daily").lower()
        if period not in {"daily", "weekly", "monthly"}:
            return success_response(
                details="Period must be daily, weekly, or monthly.",
                code="INVALID_REPORT_PERIOD",
                status_code=400,
                data={},
            )

        shop_id = request.query_params.get("shop") or request.user.active_shop_id
        if not shop_id:
            return success_response(
                details="Shop ID is required.",
                code="SHOP_ID_REQUIRED",
                status_code=400,
                data={},
            )
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)

        today = timezone.localdate()
        if period == "daily":
            start_date = end_date = today
        elif period == "weekly":
            start_date = today - datetime.timedelta(days=today.weekday())
            end_date = start_date + datetime.timedelta(days=6)
        else:
            start_date = today.replace(day=1)
            next_month = (start_date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
            end_date = next_month - datetime.timedelta(days=1)

        completed = Appointment.objects.filter(
            booking__shop=shop,
            status="completed",
            appointment_date__range=(start_date, end_date),
        )
        summary = completed.aggregate(
            revenue=Sum("price"),
            appointments=Count("id"),
        )

        staff_rows = completed.values(
            "barber_id", "barber__user__full_name", "barber__user__username"
        ).annotate(
            appointments=Count("id"),
            revenue=Sum("price"),
        ).order_by("barber__user__full_name", "barber__user__username")

        bookings = Booking.objects.filter(shop=shop, appointments__in=completed).distinct()
        total_tips = bookings.aggregate(tips=Sum("tip_amount"))["tips"] or Decimal("0")

        tips_by_barber = {}
        for booking in bookings.prefetch_related("appointments"):
            first_appointment = booking.appointments.first()
            if first_appointment:
                barber_id = first_appointment.barber_id
                tips_by_barber[barber_id] = tips_by_barber.get(barber_id, Decimal("0")) + booking.tip_amount

        staff_breakdown = [
            {
                "id": row["barber_id"],
                "name": row["barber__user__full_name"] or row["barber__user__username"],
                "appointments": row["appointments"],
                "revenue": float(row["revenue"] or Decimal("0")),
                "tips": float(tips_by_barber.get(row["barber_id"], Decimal("0"))),
            }
            for row in staff_rows
        ]

        data = {
            "shop": {"id": shop.id, "name": shop.name},
            "period": period,
            "date_range": {"start": start_date, "end": end_date},
            "total_revenue": float(summary["revenue"] or Decimal("0")),
            "total_tips": float(total_tips),
            "walk_in_orders": bookings.filter(source=Booking.SOURCE_WALK_IN).count(),
            "appointments": summary["appointments"] or 0,
            "staff_breakdown": staff_breakdown,
        }
        return success_response(details="Report retrieved successfully.", code="REPORT_RETRIEVED", data=data)