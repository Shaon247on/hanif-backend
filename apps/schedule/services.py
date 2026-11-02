"""
Effective schedule calculation.

Every screen and booking rule reads schedules through this module, so a date can only
ever resolve one way:

    Shop:   full-day business off > date override > recurring business hours
    Barber: full-day time off / day off > date override > recurring shift

Recurring records are never written from here; date-specific records live in
ShopBusinessHourOverride, BarberShiftOverride and dated BarberBreak rows.
"""

import datetime

from django.utils import timezone

from apps.booking.models import Appointment
from apps.schedule.models import BarberBreak, BarberShift, BarberShiftOverride, BarberTimeOff
from apps.shop.models import BusinessHour, BusinessOff, ShopBusinessHourOverride

ACTIVE_APPOINTMENT_STATUSES = ["scheduled", "in_progress"]
DAYS_OF_WEEK = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
SLOT_STEP_MINUTES = 15
CONFLICT_LOOKAHEAD_DAYS = 90

# Why a barber is not bookable on a date.
STATUS_WORKING = "working"
STATUS_SHOP_CLOSED = "shop_closed"
STATUS_DAY_OFF = "day_off"
STATUS_TIME_OFF = "time_off"
STATUS_NO_SHIFT = "no_shift"


def weekday_name(target_date) -> str:
    return target_date.strftime("%A").lower()


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return max(start_a, start_b) < min(end_a, end_b)


class ScheduleService:
    @staticmethod
    def get_shop_hours(shop, target_date) -> dict:
        """Resolve the hours a shop actually keeps on a date."""
        hours = {
            "source": "none",
            "is_closed": True,
            "open_time": None,
            "close_time": None,
            "breaks": [],
            "closures": [],
            "closure_reason": "",
        }

        offs = BusinessOff.objects.filter(
            shop=shop, start_date__lte=target_date, end_date__gte=target_date, is_active=True
        )
        for off in offs:
            if off.is_full_day:
                hours.update(source="closure", closure_reason=off.reason, closures=[], breaks=[])
                return hours
            hours["closures"].append(
                {"id": off.id, "start_time": off.start_time, "end_time": off.end_time, "reason": off.reason}
            )

        override = ShopBusinessHourOverride.objects.filter(shop=shop, date=target_date).first()
        effective = override or BusinessHour.objects.filter(shop=shop, day_of_week=weekday_name(target_date)).first()
        if not effective:
            return hours

        hours["source"] = "custom" if override else "recurring"
        if effective.is_closed or not effective.open_time or not effective.close_time:
            return hours

        hours.update(
            is_closed=False,
            open_time=effective.open_time,
            close_time=effective.close_time,
            breaks=[
                {"id": item.id, "start_time": item.start_time, "end_time": item.end_time}
                for item in effective.breaks.all()
            ],
        )
        return hours

    @staticmethod
    def get_barber_breaks(barber, target_date) -> list:
        """Recurring breaks for the weekday plus any added for this date only."""
        recurring = BarberBreak.objects.filter(
            barber=barber, day_of_week=weekday_name(target_date), break_date__isnull=True, is_active=True
        )
        dated = BarberBreak.objects.filter(barber=barber, break_date=target_date, is_active=True)
        return sorted([*recurring, *dated], key=lambda item: item.start_time)

    @staticmethod
    def get_barber_schedule(barber, target_date, shop_hours=None) -> dict:
        """Resolve a barber's working window, breaks and time off for a date."""
        shop_hours = shop_hours or ScheduleService.get_shop_hours(barber.shop, target_date)
        recurring = BarberShift.objects.filter(
            barber=barber, day_of_week=weekday_name(target_date), shift_date__isnull=True, is_active=True
        ).first()
        override = BarberShiftOverride.objects.filter(barber=barber, date=target_date, is_active=True).first()
        time_off = list(
            BarberTimeOff.objects.filter(
                barber=barber, start_date__lte=target_date, end_date__gte=target_date, status="approved"
            )
        )

        schedule = {
            "status": STATUS_WORKING,
            "is_working": False,
            "source": "custom" if override else "recurring",
            "start_time": None,
            "end_time": None,
            "recurring_shift": recurring,
            "override": override,
            "inherited_breaks": shop_hours["breaks"],
            "breaks": ScheduleService.get_barber_breaks(barber, target_date),
            "time_off": time_off,
        }

        if shop_hours["is_closed"]:
            return {**schedule, "status": STATUS_SHOP_CLOSED}
        if override and (override.is_off or not override.start_time or not override.end_time):
            return {**schedule, "status": STATUS_DAY_OFF}
        if any(item.is_full_day for item in time_off):
            return {**schedule, "status": STATUS_TIME_OFF}

        shift = override or recurring
        if not shift:
            return {**schedule, "status": STATUS_NO_SHIFT}

        start_time = max(shop_hours["open_time"], shift.start_time)
        end_time = min(shop_hours["close_time"], shift.end_time)
        if start_time >= end_time:
            return {**schedule, "status": STATUS_NO_SHIFT}

        return {**schedule, "is_working": True, "start_time": start_time, "end_time": end_time}

    @staticmethod
    def get_barber_availability(barber, target_date, *, include_appointments=True, exclude_booking=None):
        """
        Return the working window and every unavailable block for a date.
        Returns None if the barber cannot be booked at all that day.
        """
        if not barber.shop:
            return None

        shop_hours = ScheduleService.get_shop_hours(barber.shop, target_date)
        schedule = ScheduleService.get_barber_schedule(barber, target_date, shop_hours)
        if not schedule["is_working"]:
            return None

        blocks = [(item["start_time"], item["end_time"]) for item in shop_hours["breaks"]]
        blocks += [(item["start_time"], item["end_time"]) for item in shop_hours["closures"]]
        blocks += [(item.start_time, item.end_time) for item in schedule["breaks"]]
        blocks += [(item.start_time, item.end_time) for item in schedule["time_off"]]

        if include_appointments:
            appointments = Appointment.objects.filter(
                barber=barber, appointment_date=target_date, status__in=ACTIVE_APPOINTMENT_STATUSES
            )
            if exclude_booking is not None:
                appointments = appointments.exclude(booking=exclude_booking)
            blocks += [(item.start_time, item.end_time) for item in appointments]

        return {"start": schedule["start_time"], "end": schedule["end_time"], "blocks": blocks}

    @staticmethod
    def get_available_slots(barber, target_date, total_duration_minutes):
        """Returns a list of available slot times (string HH:MM:SS)"""
        today = timezone.localdate()
        if target_date < today:
            return []

        avail = ScheduleService.get_barber_availability(barber, target_date)
        if not avail:
            return []

        available_slots = []
        current_dt = datetime.datetime.combine(target_date, avail["start"])
        end_dt = datetime.datetime.combine(target_date, avail["end"])
        step = datetime.timedelta(minutes=SLOT_STEP_MINUTES)
        duration_delta = datetime.timedelta(minutes=total_duration_minutes)
        now_time = timezone.localtime().time() if target_date == today else None

        blocks = [
            (datetime.datetime.combine(target_date, start), datetime.datetime.combine(target_date, end))
            for start, end in avail["blocks"]
        ]

        while current_dt + duration_delta <= end_dt:
            slot_end = current_dt + duration_delta
            is_past = now_time is not None and current_dt.time() <= now_time
            if not is_past and not any(_overlaps(current_dt, slot_end, start, end) for start, end in blocks):
                available_slots.append(current_dt.time().strftime("%H:%M:%S"))
            current_dt += step

        return available_slots

    @staticmethod
    def is_slot_available(
        barber, target_date, start_time, total_duration_minutes, *, exclude_booking=None, starts_now=False
    ):
        """
        Checks if a specific start time is available for the given duration.
        `starts_now` is for a walk-in sitting down right away, whose start is this very minute.
        """
        now = timezone.localtime()
        is_past = target_date < now.date() or (target_date == now.date() and start_time <= now.time())
        if is_past and not starts_now:
            return False

        avail = ScheduleService.get_barber_availability(barber, target_date, exclude_booking=exclude_booking)
        if not avail:
            return False

        req_start_dt = datetime.datetime.combine(target_date, start_time)
        req_end_dt = req_start_dt + datetime.timedelta(minutes=total_duration_minutes)
        if req_end_dt.date() != target_date:
            return False

        return ScheduleService._fits(avail, req_start_dt.time(), req_end_dt.time())

    @staticmethod
    def _fits(avail, start_time, end_time) -> bool:
        if start_time < avail["start"] or end_time > avail["end"]:
            return False
        return not any(_overlaps(start_time, end_time, block_start, block_end) for block_start, block_end in avail["blocks"])

    @staticmethod
    def find_booking_conflicts(*, shop=None, barber=None, start_date=None, end_date=None) -> list:
        """Upcoming appointments that no longer fit the schedule. They are reported, never cancelled."""
        today = timezone.localdate()
        start_date = max(start_date or today, today)
        end_date = end_date or today + datetime.timedelta(days=CONFLICT_LOOKAHEAD_DAYS)

        appointments = Appointment.objects.filter(
            status__in=ACTIVE_APPOINTMENT_STATUSES, appointment_date__range=(start_date, end_date)
        ).select_related("booking__customer", "barber__user", "barber__shop", "service")
        if barber is not None:
            appointments = appointments.filter(barber=barber)
        if shop is not None:
            appointments = appointments.filter(booking__shop=shop)

        availability_by_day = {}
        conflicts = []
        for appointment in appointments.order_by("appointment_date", "start_time"):
            key = (appointment.barber_id, appointment.appointment_date)
            if key not in availability_by_day:
                availability_by_day[key] = ScheduleService.get_barber_availability(
                    appointment.barber, appointment.appointment_date, include_appointments=False
                )
            avail = availability_by_day[key]
            if avail and ScheduleService._fits(avail, appointment.start_time, appointment.end_time):
                continue

            customer = appointment.booking.customer
            barber_user = appointment.barber.user
            conflicts.append(
                {
                    "booking_id": appointment.booking_id,
                    "booking_code": appointment.booking.booking_code,
                    "appointment_id": appointment.id,
                    "date": appointment.appointment_date,
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "barber": barber_user.full_name or barber_user.username,
                    "customer": customer.full_name or customer.username,
                    "service": appointment.service.name,
                }
            )
        return conflicts

    @staticmethod
    def create_default_shifts(barber) -> None:
        """Give a barber a recurring shift for any weekday missing one, following the shop's hours."""
        existing_days = set(
            BarberShift.objects.filter(barber=barber, shift_date__isnull=True).values_list("day_of_week", flat=True)
        )
        shop_hours = {hour.day_of_week: hour for hour in BusinessHour.objects.filter(shop=barber.shop)}

        new_shifts = []
        for day in DAYS_OF_WEEK:
            if day in existing_days:
                continue
            start_time, end_time = datetime.time(9, 0), datetime.time(17, 0)
            hour = shop_hours.get(day)
            if hour and hour.is_closed:
                start_time = end_time = datetime.time(0, 0)
            elif hour and hour.open_time and hour.close_time:
                start_time, end_time = hour.open_time, hour.close_time
            new_shifts.append(
                BarberShift(
                    barber=barber,
                    day_of_week=day,
                    start_time=start_time,
                    end_time=end_time,
                    is_active=start_time != end_time,
                )
            )
        BarberShift.objects.bulk_create(new_shifts)
