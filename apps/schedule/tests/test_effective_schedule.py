"""The scheduling scenarios from the business brief, checked through the API."""

import datetime

from django.test import TestCase
from django.utils import timezone

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking
from apps.core.test_utils import BaseAPITestCase
from apps.schedule.models import BarberBreak, BarberShift, BarberShiftOverride, BarberTimeOff
from apps.schedule.services import ScheduleService
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessHour, BusinessHourBreak, BusinessOff, Shop, ShopBusinessHourOverride
from apps.user.enums import UserRole

# All Wednesdays. WEDNESDAY is the date that gets changed; OTHER_WEDNESDAY must never move.
WEDNESDAY = "2037-11-04"
OTHER_WEDNESDAY = "2037-11-11"
THURSDAY = "2037-11-05"


def t(value):
    return datetime.time(*[int(part) for part in value.split(":")])


class ScheduleTestCase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(email="admin@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(owner=self.admin, name="Shop", location="Dhaka")
        self.manager = self.create_user(email="manager@example.com", role=UserRole.MANAGER)
        self.shop.managers.add(self.manager)
        self.barber = Barber.objects.create(
            user=self.create_user(email="barber@example.com", role=UserRole.BARBER), shop=self.shop
        )
        self.customer = self.create_user(email="customer@example.com", role=UserRole.USER)
        category = ServiceCategory.objects.create(shop=self.shop, name="Hair")
        self.service = Service.objects.create(
            shop=self.shop, category=category, name="Cut", price="30.00", duration_minutes=30
        )

        for day, _ in BusinessHour.DAY_CHOICES:
            hour = BusinessHour.objects.create(
                shop=self.shop, day_of_week=day, open_time=t("09:00"), close_time=t("21:00")
            )
            BusinessHourBreak.objects.create(business_hour=hour, start_time=t("13:00"), end_time=t("14:00"))
            BarberShift.objects.create(barber=self.barber, day_of_week=day, start_time=t("09:00"), end_time=t("18:00"))

        self.authenticate(user=self.manager)

    def slots(self, date, barber=None):
        response = self.client.get(
            f"/api/v1/bookings/available-slots/?barber_id={(barber or self.barber).id}"
            f"&date={date}&services={self.service.id}"
        )
        return self.assert_success(response)["data"]

    def book(self, date, start, **overrides):
        payload = {
            "customer_id": str(self.customer.id),
            "shop": self.shop.id,
            "barber": self.barber.id,
            "services": [self.service.id],
            "appointment_date": date,
            "start_time": start,
            **overrides,
        }
        return self.client.post("/api/v1/bookings/", payload, format="json")

    def opening_calendar(self, date):
        response = self.client.get(f"/api/v1/schedule/opening-calendar/?shop={self.shop.id}&date={date}")
        return self.assert_success(response)["data"]

    def save_date_hours(self, **body):
        return self.client.put(
            f"/api/v1/schedule/business-hours/{self.shop.id}/", {"date": WEDNESDAY, **body}, format="json"
        )

    def save_barber_day(self, **body):
        payload = {"barber": self.barber.id, "date": WEDNESDAY, **body}
        return self.client.put("/api/v1/schedule/barber-schedule/", payload, format="json")


class BusinessHourOverrideTests(ScheduleTestCase):
    def test_date_override_only_changes_that_date(self):
        self.assert_success(
            self.save_date_hours(
                open_time="10:00:00",
                close_time="22:00:00",
                breaks=[{"start_time": "15:00:00", "end_time": "16:00:00"}],
            )
        )

        recurring = BusinessHour.objects.get(shop=self.shop, day_of_week="wednesday")
        self.assertEqual((recurring.open_time, recurring.close_time), (t("09:00"), t("21:00")))
        self.assertEqual(recurring.breaks.get().start_time, t("13:00"))

        changed = self.opening_calendar(WEDNESDAY)["shop_hours"]
        self.assertEqual(changed["source"], "custom")
        self.assertEqual((changed["open_time"], changed["close_time"]), ("10:00:00", "22:00:00"))

        other = self.opening_calendar(OTHER_WEDNESDAY)["shop_hours"]
        self.assertEqual(other["source"], "recurring")
        self.assertEqual((other["open_time"], other["close_time"]), ("09:00:00", "21:00:00"))

    def test_booking_slots_follow_the_override(self):
        self.save_date_hours(
            open_time="10:00:00",
            close_time="17:00:00",
            breaks=[{"start_time": "15:00:00", "end_time": "16:00:00"}],
        )

        slots = self.slots(WEDNESDAY)
        self.assertEqual(slots[0], "10:00:00")
        self.assertEqual(slots[-1], "16:30:00")
        self.assertIn("13:00:00", slots)
        self.assertNotIn("15:00:00", slots)

        other = self.slots(OTHER_WEDNESDAY)
        self.assertEqual(other[0], "09:00:00")
        self.assertNotIn("13:00:00", other)

    def test_override_keeps_the_regular_break_when_none_is_sent(self):
        self.assert_success(self.save_date_hours(open_time="10:00:00", close_time="20:00:00"))
        self.assertNotIn("13:00:00", self.slots(WEDNESDAY))

    def test_override_can_remove_the_break_on_purpose(self):
        self.assert_success(self.save_date_hours(open_time="10:00:00", close_time="20:00:00", breaks=[]))
        self.assertIn("13:00:00", self.slots(WEDNESDAY))

    def test_shop_can_be_closed_for_one_date(self):
        self.assert_success(self.save_date_hours(is_closed=True))
        self.assertEqual(self.slots(WEDNESDAY), [])
        self.assertTrue(self.slots(OTHER_WEDNESDAY))

    def test_reset_returns_to_recurring_hours(self):
        self.save_date_hours(is_closed=True)
        response = self.client.delete(f"/api/v1/schedule/business-hours/{self.shop.id}/?date={WEDNESDAY}")
        self.assert_success(response)
        self.assertEqual(self.opening_calendar(WEDNESDAY)["shop_hours"]["source"], "recurring")
        self.assertTrue(self.slots(WEDNESDAY))

    def test_recurring_change_applies_to_every_matching_day_without_touching_overrides(self):
        self.save_date_hours(open_time="10:00:00", close_time="20:00:00")
        response = self.client.put(
            f"/api/v1/schedule/business-hours/{self.shop.id}/",
            [{"day_of_week": "wednesday", "open_time": "11:00:00", "close_time": "19:00:00", "breaks": []}],
            format="json",
        )
        self.assert_success(response)

        self.assertEqual(self.opening_calendar(OTHER_WEDNESDAY)["shop_hours"]["open_time"], "11:00:00")
        self.assertEqual(self.opening_calendar(WEDNESDAY)["shop_hours"]["open_time"], "10:00:00")

    def test_invalid_hours_are_rejected(self):
        self.assert_error(self.save_date_hours(open_time="20:00:00", close_time="10:00:00"))
        self.assert_error(self.save_date_hours(open_time="10:00:00"))
        self.assert_error(
            self.save_date_hours(
                open_time="10:00:00",
                close_time="20:00:00",
                breaks=[{"start_time": "09:00:00", "end_time": "11:00:00"}],
            )
        )
        self.assert_error(
            self.save_date_hours(
                open_time="10:00:00",
                close_time="20:00:00",
                breaks=[
                    {"start_time": "12:00:00", "end_time": "13:00:00"},
                    {"start_time": "12:30:00", "end_time": "14:00:00"},
                ],
            )
        )
        self.assertFalse(ShopBusinessHourOverride.objects.exists())

    def test_full_day_business_off_wins_over_an_override(self):
        self.save_date_hours(open_time="10:00:00", close_time="20:00:00")
        BusinessOff.objects.create(
            shop=self.shop,
            start_date=datetime.date(2037, 11, 4),
            end_date=datetime.date(2037, 11, 4),
            reason="Holiday",
        )

        hours = self.opening_calendar(WEDNESDAY)["shop_hours"]
        self.assertTrue(hours["is_closed"])
        self.assertEqual(hours["closure_reason"], "Holiday")
        self.assertEqual(self.slots(WEDNESDAY), [])

        calendar = self.client.get(
            f"/api/v1/booking/?view_type=admin&shop_id={self.shop.id}&date={WEDNESDAY}&display_mode=calendar"
        )
        self.assertTrue(self.assert_success(calendar)["data"]["business_hours"]["is_closed"])


class StaffScheduleTests(ScheduleTestCase):
    def test_one_days_shift_change_leaves_other_weeks_alone(self):
        self.assert_success(self.save_barber_day(shift={"start_time": "10:00:00", "end_time": "19:00:00"}))

        self.assertEqual(self.slots(WEDNESDAY)[0], "10:00:00")
        self.assertEqual(self.slots(WEDNESDAY)[-1], "18:30:00")
        self.assertEqual(self.slots(OTHER_WEDNESDAY)[0], "09:00:00")
        self.assertEqual(self.slots(OTHER_WEDNESDAY)[-1], "17:30:00")

        recurring = BarberShift.objects.get(barber=self.barber, day_of_week="wednesday")
        self.assertEqual((recurring.start_time, recurring.end_time), (t("09:00"), t("18:00")))
        self.assertFalse(BarberShift.objects.filter(shift_date__isnull=False).exists())

    def test_day_off_shows_everywhere_and_blocks_booking(self):
        self.assert_success(self.save_barber_day(shift={"is_off": True}))

        self.assertEqual(self.slots(WEDNESDAY), [])
        staff = self.opening_calendar(WEDNESDAY)["staff_shifts"][0]
        self.assertEqual(staff["status"], "day_off")
        self.assertEqual(staff["shift_time"], [])

        calendar = self.client.get(
            f"/api/v1/booking/?view_type=admin&shop_id={self.shop.id}&date={WEDNESDAY}&display_mode=calendar"
        )
        self.assertEqual(self.assert_success(calendar)["data"]["barbers"][0]["shifts"], [])

        self.assertEqual(self.opening_calendar(OTHER_WEDNESDAY)["staff_shifts"][0]["status"], "working")

    def test_barber_inherits_the_shop_break_automatically(self):
        self.assertFalse(BarberBreak.objects.exists())
        slots = self.slots(WEDNESDAY)
        self.assertNotIn("13:00:00", slots)
        self.assertNotIn("13:30:00", slots)
        self.assertIn("14:00:00", slots)

    def test_additional_break_adds_to_the_inherited_break(self):
        response = self.client.post(
            "/api/v1/schedule/breaks/",
            {"barber": self.barber.id, "day_of_week": "wednesday", "start_time": "16:00", "end_time": "16:30"},
            format="json",
        )
        self.assert_success(response)

        slots = self.slots(WEDNESDAY)
        self.assertNotIn("13:00:00", slots)
        self.assertNotIn("16:00:00", slots)
        self.assertIn("15:00:00", slots)

    def test_dated_break_adds_to_recurring_breaks(self):
        BarberBreak.objects.create(
            barber=self.barber, day_of_week="wednesday", start_time=t("10:00"), end_time=t("10:30")
        )
        self.assert_success(self.save_barber_day(breaks=[{"start_time": "16:00:00", "end_time": "16:30:00"}]))

        slots = self.slots(WEDNESDAY)
        self.assertNotIn("10:00:00", slots)
        self.assertNotIn("16:00:00", slots)
        self.assertIn("16:00:00", self.slots(OTHER_WEDNESDAY))

    def test_saving_a_shift_keeps_time_off_and_breaks_that_were_not_sent(self):
        timeoff = BarberTimeOff.objects.create(
            barber=self.barber,
            start_date=datetime.date(2037, 11, 4),
            end_date=datetime.date(2037, 11, 4),
            is_full_day=False,
            start_time=t("10:00"),
            end_time=t("11:00"),
            status="approved",
            reason="Dentist",
        )
        self.save_barber_day(breaks=[{"start_time": "16:00:00", "end_time": "16:30:00"}])

        self.assert_success(
            self.save_barber_day(shift={"start_time": "09:00:00", "end_time": "17:00:00"}, time_off=[])
        )

        self.assertTrue(BarberTimeOff.objects.filter(pk=timeoff.pk).exists())
        self.assertTrue(BarberBreak.objects.filter(break_date=datetime.date(2037, 11, 4)).exists())

    def test_saving_a_weekday_again_updates_instead_of_duplicating(self):
        payload = {"barber": self.barber.id, "day_of_week": "wednesday", "start_time": "10:00", "end_time": "17:00"}
        self.assert_success(self.client.post("/api/v1/schedule/shifts/", payload, format="json"))
        self.assertEqual(BarberShift.objects.filter(barber=self.barber, day_of_week="wednesday").count(), 1)
        self.assertEqual(self.slots(WEDNESDAY)[0], "10:00:00")

    def test_turning_a_weekday_off_takes_effect(self):
        payload = {
            "barber": self.barber.id,
            "day_of_week": "wednesday",
            "start_time": "00:00",
            "end_time": "00:00",
            "is_active": False,
        }
        self.assert_success(self.client.post("/api/v1/schedule/shifts/", payload, format="json"))
        self.assertEqual(self.slots(WEDNESDAY), [])
        self.assertTrue(self.slots(THURSDAY))

    def test_recurring_shift_must_stay_within_shop_hours(self):
        payload = {"barber": self.barber.id, "day_of_week": "wednesday", "start_time": "08:00", "end_time": "22:00"}
        self.assert_error(self.client.post("/api/v1/schedule/shifts/", payload, format="json"))

    def test_date_shift_is_checked_against_that_dates_hours(self):
        self.assert_error(self.save_barber_day(shift={"start_time": "08:00:00", "end_time": "12:00:00"}))
        self.save_date_hours(open_time="07:00:00", close_time="20:00:00")
        self.assert_success(self.save_barber_day(shift={"start_time": "08:00:00", "end_time": "12:00:00"}))

        self.save_date_hours(is_closed=True)
        self.assert_error(self.save_barber_day(shift={"start_time": "08:00:00", "end_time": "12:00:00"}))

    def test_duty_out_must_follow_duty_in(self):
        self.assert_error(self.save_barber_day(shift={"start_time": "17:00:00", "end_time": "09:00:00"}))
        self.assertFalse(BarberShiftOverride.objects.exists())

    def test_break_must_fall_within_the_shift(self):
        payload = {"barber": self.barber.id, "day_of_week": "wednesday", "start_time": "19:00", "end_time": "19:30"}
        self.assert_error(self.client.post("/api/v1/schedule/breaks/", payload, format="json"))

    def test_reset_returns_the_barber_to_regular_hours(self):
        self.save_barber_day(
            shift={"start_time": "10:00:00", "end_time": "12:00:00"},
            breaks=[{"start_time": "10:30:00", "end_time": "11:00:00"}],
        )
        response = self.client.delete(f"/api/v1/schedule/barber-schedule/?barber={self.barber.id}&date={WEDNESDAY}")
        self.assert_success(response)
        self.assertEqual(self.slots(WEDNESDAY)[0], "09:00:00")
        self.assertFalse(self.opening_calendar(WEDNESDAY)["staff_shifts"][0]["is_override"])

    def test_opening_calendar_lists_all_staff_details(self):
        self.save_barber_day(
            shift={"start_time": "10:00:00", "end_time": "19:00:00"},
            breaks=[{"start_time": "16:00:00", "end_time": "16:30:00"}],
        )
        staff = self.opening_calendar(WEDNESDAY)["staff_shifts"][0]
        self.assertTrue(staff["is_override"])
        self.assertEqual(staff["shift_time"][0]["start_time"], "10:00:00")
        self.assertEqual(staff["recurring_shift"]["start_time"], "09:00:00")
        self.assertEqual(staff["inherited_breaks"][0]["start_time"], "13:00:00")
        self.assertEqual(staff["breaks"][0]["start_time"], "16:00:00")


class TimeOffTests(ScheduleTestCase):
    def add_time_off(self, **body):
        payload = {"barber": self.barber.id, "reason": "Personal", **body}
        return self.client.post("/api/v1/schedule/time-off/", payload, format="json")

    def test_hourly_time_off_blocks_those_hours_only(self):
        response = self.add_time_off(
            start_date=WEDNESDAY, is_full_day=False, start_time="10:00:00", end_time="12:00:00"
        )
        self.assert_success(response)

        slots = self.slots(WEDNESDAY)
        self.assertNotIn("10:00:00", slots)
        self.assertNotIn("11:30:00", slots)
        self.assertIn("09:00:00", slots)
        self.assertIn("12:00:00", slots)

    def test_full_day_time_off(self):
        self.assert_success(self.add_time_off(start_date=WEDNESDAY))
        self.assertEqual(self.slots(WEDNESDAY), [])
        self.assertEqual(self.opening_calendar(WEDNESDAY)["staff_shifts"][0]["status"], "time_off")
        self.assertTrue(self.slots(THURSDAY))

    def test_multiple_day_time_off(self):
        self.assert_success(self.add_time_off(start_date="2037-11-10", end_date="2037-11-12"))
        for date in ("2037-11-10", "2037-11-11", "2037-11-12"):
            self.assertEqual(self.slots(date), [])
        self.assertTrue(self.slots("2037-11-13"))

    def test_pending_request_does_not_block_until_approved(self):
        timeoff = BarberTimeOff.objects.create(
            barber=self.barber,
            start_date=datetime.date(2037, 11, 4),
            end_date=datetime.date(2037, 11, 4),
            reason="x",
        )
        self.assertTrue(self.slots(WEDNESDAY))

        response = self.client.patch(
            f"/api/v1/schedule/time-off/{timeoff.id}/approval/", {"status": "approved"}, format="json"
        )
        self.assert_success(response)
        self.assertEqual(self.slots(WEDNESDAY), [])

    def test_time_off_is_not_bookable(self):
        self.add_time_off(start_date=WEDNESDAY, is_full_day=False, start_time="10:00:00", end_time="12:00:00")
        self.assert_error(self.book(WEDNESDAY, "10:30:00"))

    def test_invalid_time_off_is_rejected(self):
        self.assert_error(self.add_time_off(start_date=THURSDAY, end_date=WEDNESDAY))
        self.assert_error(self.add_time_off(start_date=WEDNESDAY, is_full_day=False))
        self.assert_error(
            self.add_time_off(start_date=WEDNESDAY, is_full_day=False, start_time="12:00:00", end_time="10:00:00")
        )

    def test_overlapping_time_off_is_rejected(self):
        self.assert_success(self.add_time_off(start_date="2037-11-10", end_date="2037-11-12"))
        self.assert_error(self.add_time_off(start_date="2037-11-12", end_date="2037-11-14"))

    def test_separate_hours_on_one_day_are_allowed(self):
        partial = {"start_date": WEDNESDAY, "is_full_day": False}
        self.assert_success(self.add_time_off(**partial, start_time="10:00:00", end_time="11:00:00"))
        self.assert_success(self.add_time_off(**partial, start_time="15:00:00", end_time="16:00:00"))
        self.assert_error(self.add_time_off(**partial, start_time="10:30:00", end_time="11:30:00"))


class BookingSafetyTests(ScheduleTestCase):
    def test_past_dates_have_no_slots_and_cannot_be_booked(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        self.assertEqual(self.slots(yesterday.isoformat()), [])
        self.assert_error(self.book(yesterday.isoformat(), "10:00:00"))

    def test_same_slot_cannot_be_booked_twice(self):
        self.assert_success(self.book(WEDNESDAY, "10:00:00"))
        self.assert_error(self.book(WEDNESDAY, "10:00:00"))
        self.assert_error(self.book(WEDNESDAY, "10:15:00"))
        self.assert_success(self.book(WEDNESDAY, "10:30:00"))

    def test_booking_cannot_fall_in_a_break(self):
        self.assert_error(self.book(WEDNESDAY, "13:00:00"))
        self.assert_error(self.book(WEDNESDAY, "12:45:00"))

    def test_reschedule_goes_through_the_same_checks(self):
        booking_id = self.assert_success(self.book(WEDNESDAY, "10:00:00"))["data"]["id"]
        self.assert_success(self.book(WEDNESDAY, "11:00:00"))

        url = f"/api/v1/bookings/{booking_id}/"
        self.assert_error(self.client.patch(url, {"start_time": "11:00:00"}, format="json"))
        self.assert_error(self.client.patch(url, {"start_time": "13:00:00"}, format="json"))

        appointment = Appointment.objects.get(booking_id=booking_id)
        self.assertEqual(appointment.start_time, t("10:00"))

        self.assert_success(self.client.patch(url, {"start_time": "12:00:00"}, format="json"))
        self.assertEqual(Appointment.objects.get(booking_id=booking_id).start_time, t("12:00"))

    def test_a_booking_can_move_within_its_own_slot(self):
        booking_id = self.assert_success(self.book(WEDNESDAY, "10:00:00"))["data"]["id"]
        response = self.client.patch(f"/api/v1/bookings/{booking_id}/", {"start_time": "10:15:00"}, format="json")
        self.assert_success(response)

    def test_reschedule_keeps_the_discount(self):
        booking_id = self.assert_success(self.book(WEDNESDAY, "10:00:00", discount="5.00"))["data"]["id"]
        self.client.patch(f"/api/v1/bookings/{booking_id}/", {"start_time": "11:00:00"}, format="json")
        self.assertEqual(str(Booking.objects.get(pk=booking_id).total_amount), "25.00")


class BookingConflictTests(ScheduleTestCase):
    def setUp(self):
        super().setUp()
        self.booking_id = self.assert_success(self.book(WEDNESDAY, "10:00:00"))["data"]["id"]

    def assert_conflict_reported(self, response):
        data = self.assert_success(response)
        self.assertEqual([item["booking_id"] for item in data["conflicts"]], [self.booking_id])
        self.assertIn("no longer fits", data["details"])
        self.assertEqual(Appointment.objects.get(booking_id=self.booking_id).status, "scheduled")

    def test_closing_the_shop_warns_and_keeps_the_booking(self):
        self.assert_conflict_reported(self.save_date_hours(is_closed=True))

    def test_changing_a_barbers_day_warns_and_keeps_the_booking(self):
        self.assert_conflict_reported(self.save_barber_day(shift={"is_off": True}))

    def test_time_off_warns_and_keeps_the_booking(self):
        response = self.client.post(
            "/api/v1/schedule/time-off/", {"barber": self.barber.id, "start_date": WEDNESDAY}, format="json"
        )
        self.assert_conflict_reported(response)

    def test_business_off_warns_and_keeps_the_booking(self):
        response = self.client.post(
            "/api/v1/schedule/business/off/",
            {"shop": self.shop.id, "start_date": WEDNESDAY, "end_date": WEDNESDAY},
            format="json",
        )
        self.assert_conflict_reported(response)

    def test_changes_that_fit_report_no_conflicts(self):
        data = self.assert_success(self.save_date_hours(open_time="09:00:00", close_time="20:00:00"))
        self.assertEqual(data["conflicts"], [])


class ShiftConsolidationMigrationTests(TestCase):
    def test_duplicates_collapse_to_the_latest_row_and_dated_shifts_become_overrides(self):
        from importlib import import_module

        from django.apps import apps as global_apps

        migration = import_module("apps.schedule.migrations.0003_unique_recurring_shifts")
        user_model = global_apps.get_model("user", "User")
        owner = user_model.objects.create(email="o@example.com", username="o")
        shop = Shop.objects.create(owner=owner, name="S", location="L")
        barber = Barber.objects.create(user=user_model.objects.create(email="b@example.com", username="b"), shop=shop)

        dated = BarberShift.objects.create(
            barber=barber, shift_date=datetime.date(2037, 11, 4), start_time=t("10:00"), end_time=t("11:00")
        )
        recurring = BarberShift.objects.create(
            barber=barber, day_of_week="monday", start_time=t("09:00"), end_time=t("17:00")
        )

        migration.consolidate_shifts(global_apps, None)

        self.assertFalse(BarberShift.objects.filter(pk=dated.pk).exists())
        self.assertTrue(BarberShift.objects.filter(pk=recurring.pk).exists())
        override = BarberShiftOverride.objects.get(barber=barber)
        self.assertEqual(override.start_time, t("10:00"))
        self.assertEqual(ScheduleService.get_barber_schedule(barber, datetime.date(2037, 11, 4))["source"], "custom")
