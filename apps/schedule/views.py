from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.barber.models import Barber
from apps.core.access import can_manage_shop, is_global_admin, require_access_shop, require_manage_shop
from apps.core.responses import error_response, success_response
from apps.core.permissions import IsAdmin, IsShopStaff
from apps.schedule.models import BarberBreak, BarberShift, BarberShiftOverride, BarberTimeOff
from apps.schedule.services import ScheduleService, weekday_name
from apps.shop.models import (
    BusinessHour,
    BusinessHourBreak,
    BusinessOff,
    Shop,
    ShopBusinessHourOverride,
    ShopBusinessHourOverrideBreak,
)

from .serializers import (
    BarberBreakSerializer,
    BarberDateShiftInputSerializer,
    BarberShiftOverrideSerializer,
    BarberShiftSerializer,
    BarberTimeOffSerializer,
    BusinessHourSerializer,
    BusinessOffSerializer,
    DateHoursInputSerializer,
    RecurringHoursInputSerializer,
    ShopBusinessHourOverrideSerializer,
    TimeRangeInputSerializer,
    validate_breaks,
)


def require_schedule_scope(user, barber_id=None, shop_id=None):
    """Listing schedules needs a barber or shop the user works in; only admins may list everything."""
    if barber_id:
        require_access_shop(user, get_object_or_404(Barber, pk=barber_id).shop_id)
    elif shop_id:
        require_access_shop(user, shop_id)
    elif not is_global_admin(user):
        raise PermissionDenied("A shop or barber is required.")


def require_manage_barbers(user, barber_ids):
    for shop_id in Barber.objects.filter(pk__in=barber_ids).values_list("shop_id", flat=True).distinct():
        require_manage_shop(user, shop_id)


def with_conflicts(response, conflicts):
    """Existing bookings are never moved by a schedule change, so the caller is told which ones are affected."""
    response.data["conflicts"] = conflicts
    if conflicts:
        count = len(conflicts)
        noun = "booking no longer fits" if count == 1 else "bookings no longer fit"
        response.data["details"] = f"{response.data['details']} {count} existing {noun} this schedule."
    return response


def business_hours_payload(hours):
    return {
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
        "breaks": hours["breaks"],
        "closures": hours["closures"],
    }


def staff_identity(request, barber):
    image = request.build_absolute_uri(barber.user.image.url) if barber.user.image else None
    return {"id": barber.id, "name": barber.user.full_name or barber.user.username, "image": image}


def minutes_between(start_time, end_time):
    return (end_time.hour * 60 + end_time.minute) - (start_time.hour * 60 + start_time.minute)


class OpeningCalendarAPIView(APIView):
    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop") or request.user.active_shop_id
        target_date = parse_date(request.query_params.get("date", ""))
        if not shop_id or not target_date:
            return success_response(details="Shop and valid date are required.", code="SHOP_DATE_REQUIRED", data={}, status_code=400)
        shop = get_object_or_404(Shop, pk=shop_id)
        require_access_shop(request.user, shop.id)

        hours = ScheduleService.get_shop_hours(shop, target_date)
        barbers = Barber.objects.filter(shop=shop).select_related("user", "shop")

        staff_shifts = []
        for barber in barbers:
            schedule = ScheduleService.get_barber_schedule(barber, target_date, hours)
            recurring = schedule["recurring_shift"]
            override = schedule["override"]
            is_working = schedule["is_working"]
            staff_shifts.append(
                {
                    "staff": staff_identity(request, barber),
                    "status": schedule["status"],
                    "is_working": is_working,
                    "is_override": override is not None,
                    "override_reason": override.reason if override else "",
                    "shift_time": (
                        [{"start_time": schedule["start_time"], "end_time": schedule["end_time"]}] if is_working else []
                    ),
                    "duration_minutes": (
                        minutes_between(schedule["start_time"], schedule["end_time"]) if is_working else 0
                    ),
                    "recurring_shift": (
                        {"start_time": recurring.start_time, "end_time": recurring.end_time} if recurring else None
                    ),
                    "inherited_breaks": schedule["inherited_breaks"],
                    "breaks": BarberBreakSerializer(schedule["breaks"], many=True).data,
                    "time_off": BarberTimeOffSerializer(
                        schedule["time_off"], many=True, context={"request": request}
                    ).data,
                }
            )

        timeoffs = BarberTimeOff.objects.filter(
            barber__shop=shop, start_date__lte=target_date, end_date__gte=target_date
        ).exclude(status__in=["rejected", "cancelled"]).select_related("barber__user")

        data = {
            "date": target_date,
            "shop": {"id": shop.id, "name": shop.name},
            "shop_hours": business_hours_payload(hours),
            "staff_shifts": staff_shifts,
            "staff_time_off": [
                {
                    "id": item.id,
                    "staff": staff_identity(request, item.barber),
                    "start_date": item.start_date,
                    "end_date": item.end_date,
                    "is_full_day": item.is_full_day,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                    "reason": item.reason,
                    "status": item.status,
                }
                for item in timeoffs
            ],
        }
        return success_response(details="Opening calendar retrieved.", code="OPENING_CALENDAR_RETRIEVED", data=data)


class BusinessHourAPIView(APIView):
    """
    GET: 7 days business hours for a shop, or the effective hours of one date.
    PUT: A list updates the recurring hours; a single date saves an override for that date only.
    DELETE: Removes a date override, returning that date to the recurring hours.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        calendar_view = request.query_params.get("calendar_view", "false").lower() == "true"
        if calendar_view:
            target_date = parse_date(request.query_params.get("date", ""))
            if not target_date:
                return success_response(
                    details="A valid date is required when calendar_view is true.",
                    code="DATE_REQUIRED",
                    data={},
                    status_code=400,
                )

            hours = ScheduleService.get_shop_hours(shop, target_date)
            payload = business_hours_payload(hours)
            return success_response(
                details="Business hours calendar retrieved.",
                code="BUSINESS_HOURS_CALENDAR_RETRIEVED",
                data={
                    "date": target_date,
                    "shop": {"id": shop.id, "name": shop.name},
                    "source": payload.pop("source"),
                    "business_hours": payload,
                },
            )
        hours = BusinessHour.objects.filter(shop=shop)
        if hours.count() == 0:
            for day in ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
                # Default hours from 09:00 to 17:00
                BusinessHour.objects.get_or_create(
                    shop=shop,
                    day_of_week=day,
                    defaults={"open_time": "09:00:00", "close_time": "17:00:00"},
                )
            hours = BusinessHour.objects.filter(shop=shop)
        serializer = BusinessHourSerializer(hours, many=True)
        return success_response(
            details="Business hours retrieved.", code="BUSINESS_HOURS_RETRIEVED", data=serializer.data
        )

    def put(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)
        data = request.data
        if isinstance(data, dict) and data.get("date"):
            return self._save_date_hours(shop, data)
        if not isinstance(data, list):
            return error_response(details="Expected a list of 7 day business hours.", code="INVALID_DATA", data={})

        serializer = RecurringHoursInputSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            for item in serializer.validated_data:
                hour_obj, _ = BusinessHour.objects.get_or_create(shop=shop, day_of_week=item["day_of_week"])
                hour_obj.is_closed = item["is_closed"]
                hour_obj.open_time = item.get("open_time", hour_obj.open_time)
                hour_obj.close_time = item.get("close_time", hour_obj.close_time)
                hour_obj.save()
                if "breaks" in item or item["is_closed"]:
                    BusinessHourBreak.objects.filter(business_hour=hour_obj).delete()
                    BusinessHourBreak.objects.bulk_create(
                        [
                            BusinessHourBreak(
                                business_hour=hour_obj,
                                start_time=break_item["start_time"],
                                end_time=break_item["end_time"],
                            )
                            for break_item in item.get("breaks", [])
                        ]
                    )

        hours = BusinessHour.objects.filter(shop=shop)
        response = success_response(
            details="Business hours updated.",
            code="BUSINESS_HOURS_UPDATED",
            data=BusinessHourSerializer(hours, many=True).data,
        )
        return with_conflicts(response, ScheduleService.find_booking_conflicts(shop=shop))

    def _save_date_hours(self, shop, data):
        serializer = DateHoursInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        item = serializer.validated_data
        target_date = item["date"]

        if item["is_closed"]:
            breaks = []
        elif "breaks" in item:
            breaks = item["breaks"]
        else:
            # A date with no break entered keeps the regular break unless it is removed on purpose.
            recurring = BusinessHour.objects.filter(shop=shop, day_of_week=weekday_name(target_date)).first()
            breaks = list(recurring.breaks.values("start_time", "end_time")) if recurring else []
            validate_breaks(breaks, item["open_time"], item["close_time"])

        with transaction.atomic():
            override, created = ShopBusinessHourOverride.objects.update_or_create(
                shop=shop,
                date=target_date,
                defaults={
                    "open_time": None if item["is_closed"] else item["open_time"],
                    "close_time": None if item["is_closed"] else item["close_time"],
                    "is_closed": item["is_closed"],
                },
            )
            override.breaks.all().delete()
            ShopBusinessHourOverrideBreak.objects.bulk_create(
                [
                    ShopBusinessHourOverrideBreak(
                        override=override, start_time=break_item["start_time"], end_time=break_item["end_time"]
                    )
                    for break_item in breaks
                ]
            )

        response = success_response(
            details="Shop date hours created." if created else "Shop date hours updated.",
            code="SHOP_DATE_HOURS_CREATED" if created else "SHOP_DATE_HOURS_UPDATED",
            data=ShopBusinessHourOverrideSerializer(override).data,
        )
        conflicts = ScheduleService.find_booking_conflicts(shop=shop, start_date=target_date, end_date=target_date)
        return with_conflicts(response, conflicts)

    def delete(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)
        target_date = parse_date(request.query_params.get("date", ""))
        if not target_date:
            return error_response(details="A valid date is required.", code="DATE_REQUIRED")

        ShopBusinessHourOverride.objects.filter(shop=shop, date=target_date).delete()
        response = success_response(
            details="This date now follows the regular business hours.", code="SHOP_DATE_HOURS_RESET", data={}
        )
        conflicts = ScheduleService.find_booking_conflicts(shop=shop, start_date=target_date, end_date=target_date)
        return with_conflicts(response, conflicts)


class BusinessOffAPIView(APIView):
    """
    GET: List all business off periods for a shop.
    POST: Create a new business off / holiday.
    PUT/PATCH: Update a business off period.
    DELETE: Delete a business off period.
    """

    permission_classes = [IsShopStaff]

    def get(self, request, pk=None, *args, **kwargs):
        if pk:
            off_obj = get_object_or_404(BusinessOff, pk=pk)
            require_access_shop(request.user, off_obj.shop_id)
            return success_response(
                details="Business off record retrieved.",
                code="BUSINESS_OFF_RETRIEVED",
                data=BusinessOffSerializer(off_obj).data,
            )

        shop_id = request.query_params.get("shop") or request.query_params.get("shop_id") or getattr(request.user, "active_shop_id", None)
        if not shop_id:
            return success_response(details="Shop ID is required.", code="SHOP_ID_REQUIRED", data=[], status_code=400)

        require_access_shop(request.user, shop_id)
        offs = BusinessOff.objects.filter(shop_id=shop_id, is_active=True).select_related("shop").order_by("-start_date")

        date_str = request.query_params.get("date")
        if date_str:
            target_date = parse_date(date_str)
            if target_date:
                offs = offs.filter(start_date__lte=target_date, end_date__gte=target_date)

        serializer = BusinessOffSerializer(offs, many=True)
        return success_response(
            details="Business off records retrieved.",
            code="BUSINESS_OFF_RETRIEVED",
            data=serializer.data,
        )

    def _conflicts(self, off_obj):
        return ScheduleService.find_booking_conflicts(
            shop=off_obj.shop, start_date=off_obj.start_date, end_date=off_obj.end_date
        )

    def post(self, request, *args, **kwargs):
        serializer = BusinessOffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_manage_shop(request.user, serializer.validated_data["shop"].id)
        off_obj = serializer.save()
        response = success_response(
            details="Business off record created.",
            code="BUSINESS_OFF_CREATED",
            data=BusinessOffSerializer(off_obj).data,
        )
        return with_conflicts(response, self._conflicts(off_obj))

    def put(self, request, pk=None, *args, **kwargs):
        off_id = pk or request.data.get("id")
        if not off_id:
            return success_response(details="Business off ID is required.", code="ID_REQUIRED", data={}, status_code=400)
        off_obj = get_object_or_404(BusinessOff, pk=off_id)
        require_manage_shop(request.user, off_obj.shop_id)
        serializer = BusinessOffSerializer(off_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "shop" in serializer.validated_data:
            require_manage_shop(request.user, serializer.validated_data["shop"].id)
        off_obj = serializer.save()
        response = success_response(
            details="Business off record updated.",
            code="BUSINESS_OFF_UPDATED",
            data=BusinessOffSerializer(off_obj).data,
        )
        return with_conflicts(response, self._conflicts(off_obj))

    patch = put

    def delete(self, request, pk=None, *args, **kwargs):
        off_id = pk or request.data.get("id") or request.query_params.get("id")
        if not off_id:
            return success_response(details="Business off ID is required.", code="ID_REQUIRED", data={}, status_code=400)
        off_obj = get_object_or_404(BusinessOff, pk=off_id)
        require_manage_shop(request.user, off_obj.shop_id)
        off_obj.delete()
        return success_response(details="Business off record deleted.", code="BUSINESS_OFF_DELETED", data={})


class BarberShiftListCreateAPIView(APIView):
    """
    GET: List shifts for barber or shop, or the effective shifts of one date.
    POST: Save the recurring shift of one or more weekdays.
    """

    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        barber_id = request.query_params.get("barber")
        shop_id = request.query_params.get("shop")
        day_of_week = request.query_params.get("day_of_week")
        date_str = request.query_params.get("date")

        require_schedule_scope(request.user, barber_id, shop_id)

        target_date = parse_date(date_str) if date_str else None

        if barber_id:
            ScheduleService.create_default_shifts(Barber.objects.select_related("shop").get(pk=barber_id))

        if target_date:
            barbers = Barber.objects.select_related("user", "shop")
            if barber_id:
                barbers = barbers.filter(pk=barber_id)
            if shop_id:
                barbers = barbers.filter(shop_id=shop_id)

            active_shifts = []
            for barber in barbers:
                schedule = ScheduleService.get_barber_schedule(barber, target_date)
                if not schedule["is_working"]:
                    continue
                shift = schedule["override"] or schedule["recurring_shift"]
                active_shifts.append(
                    {
                        "id": shift.id,
                        "barber": barber.id,
                        "barber_name": barber.user.full_name or barber.user.username,
                        "day_of_week": weekday_name(target_date),
                        "shift_date": target_date,
                        "start_time": schedule["start_time"],
                        "end_time": schedule["end_time"],
                        "is_active": True,
                        "is_override": schedule["override"] is not None,
                    }
                )
            return success_response(details="Shifts retrieved.", code="SHIFTS_RETRIEVED", data=active_shifts)

        shifts = BarberShift.objects.filter(shift_date__isnull=True)
        if barber_id:
            shifts = shifts.filter(barber_id=barber_id)
        if shop_id:
            shifts = shifts.filter(barber__shop_id=shop_id)
        if day_of_week:
            shifts = shifts.filter(day_of_week=day_of_week.lower())

        shifts = shifts.select_related("barber", "barber__user").order_by("barber_id", "day_of_week", "start_time")
        return success_response(
            details="Shifts retrieved.",
            code="SHIFTS_RETRIEVED",
            data=BarberShiftSerializer(shifts, many=True).data,
        )

    def _conflicts(self, barbers):
        conflicts = []
        for barber in {item.pk: item for item in barbers}.values():
            conflicts += ScheduleService.find_booking_conflicts(barber=barber)
        return conflicts

    def post(self, request, *args, **kwargs):
        data = request.data
        if isinstance(data, list):
            serializer = BarberShiftSerializer(data=data, many=True)
            serializer.is_valid(raise_exception=True)
            barbers = [item["barber"] for item in serializer.validated_data]
            require_manage_barbers(request.user, [barber.id for barber in barbers])
            shifts = serializer.save()
            response = success_response(
                details="Shifts added successfully.",
                code="SHIFTS_ADDED",
                data=BarberShiftSerializer(shifts, many=True).data,
            )
            return with_conflicts(response, self._conflicts(barbers))

        serializer = BarberShiftSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        barber = serializer.validated_data["barber"]
        require_manage_barbers(request.user, [barber.id])
        shift = serializer.save()
        response = success_response(
            details="Shift added successfully.",
            code="SHIFT_ADDED",
            data=BarberShiftSerializer(shift).data,
        )
        return with_conflicts(response, self._conflicts([barber]))


class BarberShiftDetailAPIView(APIView):
    """
    GET: Retrieve a single barber shift.
    PATCH/PUT: Update a barber shift.
    DELETE: Delete a barber shift.
    """

    permission_classes = [IsShopStaff]

    def get(self, request, pk, *args, **kwargs):
        shift = get_object_or_404(BarberShift, pk=pk)
        require_access_shop(request.user, shift.barber.shop_id)
        return success_response(
            details="Shift retrieved.",
            code="SHIFT_RETRIEVED",
            data=BarberShiftSerializer(shift).data,
        )

    def patch(self, request, pk, *args, **kwargs):
        shift = get_object_or_404(BarberShift, pk=pk)
        require_manage_shop(request.user, shift.barber.shop_id)
        serializer = BarberShiftSerializer(shift, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "barber" in serializer.validated_data:
            require_manage_barbers(request.user, [serializer.validated_data["barber"].id])
        serializer.save()
        response = success_response(details="Shift updated.", code="SHIFT_UPDATED", data=serializer.data)
        return with_conflicts(response, ScheduleService.find_booking_conflicts(barber=shift.barber))

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)

    def delete(self, request, pk, *args, **kwargs):
        shift = get_object_or_404(BarberShift, pk=pk)
        require_manage_shop(request.user, shift.barber.shop_id)
        shift.delete()
        return success_response(details="Shift deleted.", code="SHIFT_DELETED", data={})


class BarberBreakListCreateAPIView(APIView):
    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        barber_id = request.query_params.get("barber")
        shop_id = request.query_params.get("shop") or request.user.active_shop_id
        date_str = request.query_params.get("date")
        require_schedule_scope(request.user, barber_id, shop_id)
        breaks = BarberBreak.objects.all()

        if shop_id:
            breaks = breaks.filter(barber__shop_id=shop_id)
        if barber_id:
            breaks = breaks.filter(barber_id=barber_id)
        target_date = None
        if date_str:
            target_date = parse_date(date_str)
            if not target_date:
                return success_response(details="Invalid date format. Use YYYY-MM-DD.", code="INVALID_DATE", data={}, status_code=400)
            weekday = weekday_name(target_date)
            breaks = breaks.filter(
                models.Q(break_date=target_date) | models.Q(break_date__isnull=True, day_of_week=weekday)
            )
        breaks = breaks.select_related("barber", "barber__user").order_by("barber_id", "start_time")

        if target_date and shop_id:
            hours = ScheduleService.get_shop_hours(get_object_or_404(Shop, pk=shop_id), target_date)
            shop_break_data = [{**item, "day_of_week": weekday_name(target_date)} for item in hours["breaks"]]
        else:
            shop_breaks = BusinessHourBreak.objects.filter(business_hour__shop_id=shop_id)
            shop_breaks = shop_breaks.select_related("business_hour").order_by("start_time")
            shop_break_data = [
                {
                    "id": item.id,
                    "day_of_week": item.business_hour.day_of_week,
                    "start_time": item.start_time,
                    "end_time": item.end_time,
                }
                for item in shop_breaks
            ]

        barbers = Barber.objects.filter(shop_id=shop_id)
        if barber_id:
            barbers = barbers.filter(pk=barber_id)
        barbers = barbers.select_related("user")
        barber_break_data = []
        for barber in barbers:
            barber_breaks = breaks.filter(barber=barber)
            time_offs = BarberTimeOff.objects.filter(
                barber=barber,
                status="approved",
            )
            today_off = False
            if target_date:
                today_off = time_offs.filter(start_date__lte=target_date, end_date__gte=target_date).exists()
            barber_break_data.append(
                {
                    "barber": {"id": barber.id, "name": barber.user.full_name or barber.user.username},
                    "breaks": BarberBreakSerializer(barber_breaks, many=True).data,
                    "today_off": today_off,
                }
            )
        return success_response(
            details="Shop and barber breaks retrieved.",
            code="BREAKS_RETRIEVED",
            data={"shop_breaks": shop_break_data, "barber_breaks": barber_break_data},
        )

    def post(self, request, *args, **kwargs):
        serializer = BarberBreakSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        barber = serializer.validated_data["barber"]
        require_manage_barbers(request.user, [barber.id])
        serializer.save()
        response = success_response(details="Break added.", code="BREAK_ADDED", data=serializer.data)
        return with_conflicts(response, ScheduleService.find_booking_conflicts(barber=barber))


class BarberBreakDetailAPIView(APIView):
    permission_classes = [IsShopStaff]

    def patch(self, request, pk, *args, **kwargs):
        b_break = get_object_or_404(BarberBreak, pk=pk)
        require_manage_shop(request.user, b_break.barber.shop_id)
        serializer = BarberBreakSerializer(b_break, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if "barber" in serializer.validated_data:
            require_manage_barbers(request.user, [serializer.validated_data["barber"].id])
        serializer.save()
        response = success_response(details="Break updated.", code="BREAK_UPDATED", data=serializer.data)
        return with_conflicts(response, ScheduleService.find_booking_conflicts(barber=b_break.barber))

    def delete(self, request, pk, *args, **kwargs):
        b_break = get_object_or_404(BarberBreak, pk=pk)
        require_manage_shop(request.user, b_break.barber.shop_id)
        b_break.delete()
        return success_response(details="Break deleted.", code="BREAK_DELETED", data={})


def time_off_conflicts(timeoffs):
    conflicts = []
    for item in timeoffs:
        if item.status == "approved":
            conflicts += ScheduleService.find_booking_conflicts(
                barber=item.barber, start_date=item.start_date, end_date=item.end_date
            )
    return conflicts


class BarberTimeOffListCreateAPIView(APIView):
    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        barber_id = request.query_params.get("barber")
        shop_id = request.query_params.get("shop") or request.user.active_shop_id
        date_str = request.query_params.get("date")
        include_schedule = request.query_params.get("schedule", "false").lower() == "true"
        require_schedule_scope(request.user, barber_id, shop_id)
        timeoffs = BarberTimeOff.objects.filter(barber_id=barber_id) if barber_id else BarberTimeOff.objects.all()
        if shop_id:
            timeoffs = timeoffs.filter(barber__shop_id=shop_id)
        target_date = None
        if date_str:
            target_date = parse_date(date_str)
            if not target_date:
                return success_response(details="Invalid date format. Use YYYY-MM-DD.", code="INVALID_DATE", data={}, status_code=400)
            timeoffs = timeoffs.filter(start_date__lte=target_date, end_date__gte=target_date)

        if include_schedule:
            barbers = Barber.objects.filter(shop_id=shop_id) if shop_id else Barber.objects.all()
            if barber_id:
                barbers = barbers.filter(pk=barber_id)
            barbers = barbers.select_related("user")
            grouped = []
            for barber in barbers:
                breaks = BarberBreak.objects.filter(barber=barber, is_active=True)
                if target_date:
                    weekday = weekday_name(target_date)
                    breaks = breaks.filter(
                        models.Q(break_date=target_date)
                        | models.Q(break_date__isnull=True, day_of_week=weekday)
                    )
                barber_timeoffs = timeoffs.filter(barber=barber)
                image = request.build_absolute_uri(barber.user.image.url) if barber.user.image else None
                grouped.append(
                    {
                        "barber": {
                            "id": barber.id,
                            "name": barber.user.full_name or barber.user.username,
                            "image": image,
                        },
                        "breaks": BarberBreakSerializer(breaks.order_by("start_time"), many=True).data,
                        "time_off": BarberTimeOffSerializer(
                            barber_timeoffs.order_by("start_date"), many=True, context={"request": request}
                        ).data,
                    }
                )
            return success_response(
                details="Barber breaks and time off retrieved.",
                code="BARBER_BREAKS_TIME_OFF_RETRIEVED",
                data=grouped,
            )
        timeoffs = timeoffs.select_related("barber__user")
        return success_response(
            details="Time off retrieved.",
            code="TIMEOFF_RETRIEVED",
            data=BarberTimeOffSerializer(timeoffs, many=True, context={"request": request}).data,
        )

    def post(self, request, *args, **kwargs):
        is_bulk = isinstance(request.data, list)
        serializer = BarberTimeOffSerializer(
            data=request.data,
            many=is_bulk,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        saved = serializer.save()
        response = success_response(
            details="Time off added." if not is_bulk else "Time offs added.",
            code="TIMEOFF_ADDED" if not is_bulk else "TIMEOFFS_ADDED",
            data=serializer.data,
        )
        return with_conflicts(response, time_off_conflicts(saved if is_bulk else [saved]))


class BarberScheduleUpdateAPIView(APIView):
    """
    PUT: Change one barber's schedule for one date. Only the parts sent are changed:
         `shift` sets duty hours or a day off, `breaks` replaces that date's additional breaks,
         `time_off` adds new records and never removes existing ones.
    DELETE: Returns the barber to their recurring shift and breaks for that date.
    """

    permission_classes = [IsShopStaff]

    def _get_barber(self, request, barber_val):
        if not barber_val:
            return Barber.objects.filter(user=request.user).first()
        # Accepts the barber's numeric id or their user UUID
        lookup = {"pk": barber_val} if str(barber_val).isdigit() else {"user_id": barber_val}
        return Barber.objects.filter(**lookup).first()

    def _resolve_shift(self, shift_data, barber, target_date):
        """Validate a date-specific shift against the shop's hours for that date."""
        serializer = BarberDateShiftInputSerializer(data=shift_data)
        serializer.is_valid(raise_exception=True)
        shift = serializer.validated_data
        if shift["is_off"]:
            return shift

        hours = ScheduleService.get_shop_hours(barber.shop, target_date)
        if hours["is_closed"]:
            raise ValidationError("The shop is closed on this date.")
        if shift["start_time"] < hours["open_time"] or shift["end_time"] > hours["close_time"]:
            raise ValidationError("Staff working hours must stay within the shop's hours for this date.")
        return shift

    def put(self, request, *args, **kwargs):
        barber = self._get_barber(
            request,
            request.data.get("barber")
            or request.data.get("barber_id")
            or request.data.get("staff")
            or request.data.get("staff_id"),
        )
        if not barber:
            return success_response(details="Barber is required.", code="BARBER_REQUIRED", data={}, status_code=400)

        require_manage_shop(request.user, barber.shop_id)

        target_date = parse_date(str(request.data.get("date", "")))
        if not target_date:
            return success_response(details="Valid date is required (YYYY-MM-DD).", code="DATE_REQUIRED", data={}, status_code=400)

        shift_data = request.data.get("shift") or request.data.get("shift_override")
        if not shift_data and "shifts" in request.data:
            shifts_list = request.data.get("shifts")
            if isinstance(shifts_list, list) and len(shifts_list) > 0:
                shift_data = shifts_list[0]
        if not shift_data and ("start_time" in request.data or "is_off" in request.data):
            shift_data = {
                "start_time": request.data.get("start_time"),
                "end_time": request.data.get("end_time"),
                "is_off": request.data.get("is_off", False),
                "reason": request.data.get("reason") or request.data.get("shift_reason", ""),
            }
        shift = self._resolve_shift(shift_data, barber, target_date) if shift_data else None

        breaks = None
        if "breaks" in request.data:
            serializer = TimeRangeInputSerializer(data=request.data["breaks"], many=True)
            serializer.is_valid(raise_exception=True)
            breaks = serializer.validated_data
            if shift:
                window_start, window_end = shift["start_time"], shift["end_time"]
            else:
                schedule = ScheduleService.get_barber_schedule(barber, target_date)
                window_start, window_end = schedule["start_time"], schedule["end_time"]
            validate_breaks(breaks, window_start, window_end)

        time_off_serializer = None
        time_off = request.data.get("time_off")
        if isinstance(time_off, dict):
            time_off = [time_off]
        if time_off:
            time_off_serializer = BarberTimeOffSerializer(
                data=[
                    {"start_date": target_date, "end_date": target_date, **item, "barber": barber.id}
                    for item in time_off
                ],
                many=True,
                context={"request": request},
            )
            time_off_serializer.is_valid(raise_exception=True)

        override_instance = None
        with transaction.atomic():
            if shift:
                override_instance, _ = BarberShiftOverride.objects.update_or_create(
                    barber=barber,
                    date=target_date,
                    defaults={
                        "start_time": shift["start_time"],
                        "end_time": shift["end_time"],
                        "is_off": shift["is_off"],
                        "is_active": True,
                        "reason": shift["reason"],
                    },
                )

            if breaks is not None:
                BarberBreak.objects.filter(barber=barber, break_date=target_date).delete()
                BarberBreak.objects.bulk_create(
                    [
                        BarberBreak(
                            barber=barber,
                            break_date=target_date,
                            day_of_week=None,
                            start_time=item["start_time"],
                            end_time=item["end_time"],
                            title=item["title"] or "Break",
                            is_active=item["is_active"],
                        )
                        for item in breaks
                    ]
                )

            if time_off_serializer:
                time_off_serializer.save()

        response = success_response(
            details="Barber schedule and shift override updated.",
            code="BARBER_SCHEDULE_UPDATED",
            data={
                "barber": barber.id,
                "barber_name": barber.user.full_name or barber.user.username,
                "date": target_date,
                "shift_override": BarberShiftOverrideSerializer(override_instance).data if override_instance else None,
            },
        )
        conflicts = ScheduleService.find_booking_conflicts(barber=barber, start_date=target_date, end_date=target_date)
        return with_conflicts(response, conflicts)

    def delete(self, request, *args, **kwargs):
        barber = self._get_barber(request, request.query_params.get("barber"))
        if not barber:
            return error_response(details="Barber is required.", code="BARBER_REQUIRED")
        require_manage_shop(request.user, barber.shop_id)

        target_date = parse_date(request.query_params.get("date", ""))
        if not target_date:
            return error_response(details="Valid date is required (YYYY-MM-DD).", code="DATE_REQUIRED")

        with transaction.atomic():
            BarberShiftOverride.objects.filter(barber=barber, date=target_date).delete()
            BarberBreak.objects.filter(barber=barber, break_date=target_date).delete()

        response = success_response(
            details="This date now follows the staff member's regular hours.", code="BARBER_SCHEDULE_RESET", data={}
        )
        conflicts = ScheduleService.find_booking_conflicts(barber=barber, start_date=target_date, end_date=target_date)
        return with_conflicts(response, conflicts)


class BarberTimeOffDetailAPIView(APIView):
    permission_classes = [IsShopStaff]

    def get_object(self, request, pk):
        """Managers edit any record in their shop; barbers only their own requests that are still pending."""
        timeoff = get_object_or_404(BarberTimeOff, pk=pk)
        is_own_pending = timeoff.barber.user_id == request.user.id and timeoff.status == "pending"
        if not is_own_pending and not can_manage_shop(request.user, timeoff.barber.shop_id):
            raise PermissionDenied("You cannot change this time off.")
        return timeoff

    def patch(self, request, pk, *args, **kwargs):
        timeoff = self.get_object(request, pk)
        serializer = BarberTimeOffSerializer(timeoff, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        saved = serializer.save()
        response = success_response(details="Time off updated.", code="TIMEOFF_UPDATED", data=serializer.data)
        return with_conflicts(response, time_off_conflicts([saved]))

    def put(self, request, *args, **kwargs):
        return self.patch(request, *args, **kwargs)

    def delete(self, request, pk, *args, **kwargs):
        timeoff = self.get_object(request, pk)
        timeoff.delete()
        return success_response(details="Time off deleted.", code="TIMEOFF_DELETED", data={})


class BarberTimeOffApprovalAPIView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk, *args, **kwargs):
        timeoff = get_object_or_404(BarberTimeOff, pk=pk)
        require_manage_shop(request.user, timeoff.barber.shop_id)
        decision = request.data.get("status")
        if decision not in {"approved", "rejected", "cancelled"}:
            return success_response(details="Invalid time-off status.", code="INVALID_STATUS", data={}, status_code=400)
        timeoff.status = decision
        timeoff.reviewed_by = request.user
        timeoff.save(update_fields=["status", "reviewed_by", "updated_at"])
        response = success_response(
            details="Time off status updated.",
            code="TIMEOFF_STATUS_UPDATED",
            data=BarberTimeOffSerializer(timeoff, context={"request": request}).data,
        )
        return with_conflicts(response, time_off_conflicts([timeoff]))
