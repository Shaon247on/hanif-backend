"""Tests for BusinessOff and BarberShift schedule APIs."""

import datetime
from apps.barber.models import Barber
from apps.core.test_utils import BaseAPITestCase
from apps.schedule.models import BarberShift
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessOff, Shop
from apps.user.enums import UserRole


class ScheduleAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.create_user(email="owner@example.com", role=UserRole.ADMIN)
        self.shop = Shop.objects.create(
            owner=self.owner,
            name="Barberbay Studio",
            location="123 Main St",
        )
        self.barber_user = self.create_user(email="barber@example.com", role="barber")
        self.barber = Barber.objects.create(
            user=self.barber_user,
            shop=self.shop,
            specialty="Master Barber",
        )
        self.category = ServiceCategory.objects.create(shop=self.shop, name="Haircuts")
        self.service = Service.objects.create(
            shop=self.shop,
            category=self.category,
            name="Classic Haircut",
            price="30.00",
            duration_minutes=30,
        )
        self.service.barbers.add(self.barber.user)
        
        from apps.shop.models import BusinessHour
        import datetime
        for day, _ in BusinessHour.DAY_CHOICES:
            BusinessHour.objects.create(shop=self.shop, day_of_week=day, open_time=datetime.time(8, 0), close_time=datetime.time(20, 0))

    def test_create_and_list_business_off(self):
        """Test creating and listing shop business off periods."""
        self.authenticate(user=self.owner)

        # Create Business Off
        payload = {
            "shop": self.shop.id,
            "start_date": "2037-09-01",
            "end_date": "2037-09-05",
            "is_full_day": True,
            "reason": "Shop Renovation & Eid Holiday",
        }
        res = self.client.post("/api/v1/schedule/business/off/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BUSINESS_OFF_CREATED")
        off_id = data["data"]["id"]
        self.assertEqual(data["data"]["reason"], "Shop Renovation & Eid Holiday")

        # List Business Off
        res = self.client.get(f"/api/v1/schedule/business/off/?shop={self.shop.id}")
        list_data = self.assert_success(res)
        self.assertEqual(len(list_data["data"]), 1)
        self.assertEqual(list_data["data"][0]["id"], off_id)

        # Update Business Off
        update_payload = {"reason": "Updated Renovation Reason"}
        res = self.client.put(f"/api/v1/schedule/business/off/{off_id}/", update_payload, format="json")
        update_data = self.assert_success(res)
        self.assertEqual(update_data["data"]["reason"], "Updated Renovation Reason")

        # Delete Business Off
        res = self.client.delete(f"/api/v1/schedule/business/off/{off_id}/")
        self.assert_success(res)
        self.assertEqual(BusinessOff.objects.filter(pk=off_id).count(), 0)

    def test_create_and_list_barber_shifts_single_and_bulk(self):
        """Test creating single and bulk shifts for a barber."""
        self.authenticate(user=self.owner)

        # Single shift creation
        payload = {
            "barber": self.barber.id,
            "day_of_week": "monday",
            "start_time": "09:00:00",
            "end_time": "18:00:00",
            "is_active": True,
        }
        res = self.client.post("/api/v1/schedule/shifts/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "SHIFT_ADDED")
        self.assertEqual(data["data"]["day_of_week"], "monday")

        # Bulk shift creation
        bulk_payload = [
            {
                "barber": self.barber.id,
                "day_of_week": "tuesday",
                "start_time": "09:00:00",
                "end_time": "18:00:00",
            },
            {
                "barber": self.barber.id,
                "day_of_week": "wednesday",
                "start_time": "10:00:00",
                "end_time": "19:00:00",
            },
        ]
        res = self.client.post("/api/v1/schedule/shifts/", bulk_payload, format="json")
        bulk_data = self.assert_success(res)
        self.assertEqual(bulk_data["code"], "SHIFTS_ADDED")
        self.assertEqual(len(bulk_data["data"]), 2)

        # List shifts by shop
        res = self.client.get(f"/api/v1/schedule/shifts/?shop={self.shop.id}")
        list_data = self.assert_success(res)
        self.assertEqual(len(list_data["data"]), 3)

    def test_availability_considers_business_off(self):
        """When shop is business off on target date, availability API returns SHOP_CLOSED."""
        self.authenticate(user=self.owner)

        # Setup active shift for Monday
        BarberShift.objects.create(
            barber=self.barber,
            day_of_week="monday",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
        )

        # 2037-09-07 is a Monday
        target_date = "2037-09-07"

        # Check availability before business off (should return slots)
        res = self.client.get(
            f"/api/v1/bookings/available-slots/?barber_id={self.barber.id}&date={target_date}&services={self.service.id}"
        )
        data = self.assert_success(res)
        self.assertTrue(len(data["data"]) > 0)

        # Add Business Off for that date
        BusinessOff.objects.create(
            shop=self.shop,
            start_date=datetime.date(2037, 9, 6),
            end_date=datetime.date(2037, 9, 8),
            is_full_day=True,
            reason="National Holiday",
        )

        # Check availability again (should return SHOP_CLOSED and empty data)
        res = self.client.get(f"/api/v1/bookings/available-slots/?barber_id={self.barber.id}&date={target_date}&services={self.service.id}")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "NO_SLOTS")
        self.assertEqual(data["data"], [])

    def test_schedule_shift_override_and_availability(self):
        """Test updating schedule shift override on a specific date and verifying list and availability."""
        self.authenticate(user=self.owner)

        # Base weekly shift: Monday 09:00 - 17:00
        BarberShift.objects.create(
            barber=self.barber,
            day_of_week="monday",
            start_time=datetime.time(9, 0),
            end_time=datetime.time(17, 0),
        )

        target_date = "2037-09-07"  # Monday

        # 1. Override shift hours on 2037-09-07 to 13:00 - 18:00
        payload = {
            "barber": self.barber.id,
            "date": target_date,
            "shift": {
                "start_time": "13:00:00",
                "end_time": "18:00:00",
                "is_off": False,
            },
        }
        res = self.client.put("/api/v1/schedule/barber/schedule/", payload, format="json")
        data = self.assert_success(res)
        self.assertEqual(data["code"], "BARBER_SCHEDULE_UPDATED")
        self.assertIsNotNone(data["data"]["shift_override"])
        self.assertEqual(data["data"]["shift_override"]["start_time"], "13:00:00")

        # 2. Check shift list API on 2037-09-07
        res_list = self.client.get(f"/api/v1/schedule/shifts/?shop={self.shop.id}&date={target_date}")
        list_data = self.assert_success(res_list)
        self.assertEqual(len(list_data["data"]), 1)
        self.assertEqual(str(list_data["data"][0]["start_time"]), "13:00:00")
        self.assertTrue(list_data["data"][0]["is_override"])

        # 3. Check booking availability on 2037-09-07 (first slot must start at 13:00)
        res_avail = self.client.get(
            f"/api/v1/bookings/available-slots/?barber_id={self.barber.id}&date={target_date}&services={self.service.id}"
        )
        avail_data = self.assert_success(res_avail)
        self.assertTrue(len(avail_data["data"]) > 0)
        self.assertEqual(avail_data["data"][0], "13:00:00")

        # 4. Override barber as OFF on 2037-09-07
        off_payload = {
            "barber": self.barber.id,
            "date": target_date,
            "shift": {
                "is_off": True,
            },
        }
        res_off = self.client.put("/api/v1/schedule/barber/schedule/", off_payload, format="json")
        self.assert_success(res_off)

        # 5. Check booking availability when barber is OFF on that date
        res_off = self.client.get(f"/api/v1/bookings/available-slots/?barber_id={self.barber.id}&date={target_date}&services={self.service.id}")
        data_off = self.assert_success(res_off)
        self.assertEqual(data_off["code"], "NO_SLOTS")
        self.assertEqual(data_off["data"], [])
