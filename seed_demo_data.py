"""Create a repeatable local demo dataset for BarberBay."""

import os
from datetime import time, timedelta
from decimal import Decimal

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.utils import timezone

from apps.barber.models import Barber
from apps.booking.models import Appointment, Booking, ShopReview
from apps.schedule.models import BarberBreak, BarberShift
from apps.service.models import Service, ServiceCategory
from apps.shop.models import BusinessHour, BusinessHourBreak, Shop
from apps.user.enums import UserRole
from apps.user.models import User


SUPER_ADMIN_EMAIL = "testadmin@gmail.com"
SUPER_ADMIN_PASSWORD = "Test!@#123"
ADMIN_EMAIL = "admin@barberbay.test"
ADMIN_PASSWORD = "Admin!@#123"
MANAGER_ACCOUNTS = [
    ("manager1@barberbay.test", "Manager!@#123", "Farhan Rahman"),
    ("manager2@barberbay.test", "Manager!@#123", "Sadia Islam"),
]
# email, password, name, specialty, index of the shop in SHOPS
STAFF_ACCOUNTS = [
    ("staff1@barberbay.test", "Staff!@#123", "Arif Hossain", "Classic cuts", 0),
    ("staff2@barberbay.test", "Staff!@#123", "Nabil Hasan", "Beard styling", 0),
    ("staff3@barberbay.test", "Staff!@#123", "Samiul Karim", "Modern fades", 1),
]
# The online gateway stays off on one shop so both payment paths can be tested.
SHOPS = [
    ("BarberBay Studio", "Dhanmondi, Dhaka", "hello@barberbay.test", True),
    ("BarberBay Downtown", "Gulshan, Dhaka", "downtown@barberbay.test", False),
]
CUSTOMER_ACCOUNTS = [
    ("customer1@barberbay.test", "User!@#123", "Rahim Ahmed"),
    ("customer2@barberbay.test", "User!@#123", "Nusrat Jahan"),
    ("customer3@barberbay.test", "User!@#123", "Tanvir Chowdhury"),
    ("customer4@barberbay.test", "User!@#123", "Mitu Sultana"),
]
DAYS = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def upsert_user(email, password, full_name, role, *, superuser=False):
    user = User.objects.filter(email=email).first()
    if user is None:
        if superuser:
            user = User.objects.create_superuser(email=email, password=password, username=email.split("@")[0])
        else:
            user = User.objects.create_user(email=email, password=password, username=email.split("@")[0], role=role)
    else:
        user.set_password(password)
        user.role = role
        user.is_active = True
        user.is_staff = superuser
        user.is_superuser = superuser
        user.save(update_fields=["password", "role", "is_active", "is_staff", "is_superuser"])
    if user.full_name != full_name:
        user.full_name = full_name
        user.save(update_fields=["full_name"])
    return user


def populate():
    today = timezone.localdate()
    super_admin = upsert_user(SUPER_ADMIN_EMAIL, SUPER_ADMIN_PASSWORD, "Test Admin", UserRole.SUPER_ADMIN, superuser=True)
    upsert_user(ADMIN_EMAIL, ADMIN_PASSWORD, "Business Admin", UserRole.ADMIN)
    managers = [
        upsert_user(email, password, name, UserRole.MANAGER)
        for email, password, name in MANAGER_ACCOUNTS
    ]
    staff_users = [
        upsert_user(email, password, name, UserRole.BARBER)
        for email, password, name, _specialty, _shop_index in STAFF_ACCOUNTS
    ]
    customers = [
        upsert_user(email, password, name, UserRole.USER)
        for email, password, name in CUSTOMER_ACCOUNTS
    ]

    shops = []
    for (name, location, email, gateway_enabled), manager in zip(SHOPS, managers):
        shop, _ = Shop.objects.update_or_create(
            name=name,
            defaults={
                "owner": super_admin,
                "location": location,
                "about_us": "A modern neighborhood barbershop for classic and contemporary styles.",
                "phone": "+8801700000000",
                "email": email,
                "whatsapp": "+8801700000000",
                "payment_gateway_enabled": gateway_enabled,
            },
        )
        shop.managers.set([manager])
        shops.append(shop)

    barbers = []
    for user, (_email, _password, _name, specialty, shop_index) in zip(staff_users, STAFF_ACCOUNTS):
        barber, _ = Barber.objects.update_or_create(
            user=user,
            defaults={
                "shop": shops[shop_index],
                "specialty": specialty,
                "bio": f"Experienced BarberBay stylist specializing in {specialty.lower()}.",
                "experience_years": 5,
                "is_available": True,
                "commission_rate": Decimal("30.00"),
                "role": "staff",
            },
        )
        barbers.append(barber)

    # Barbers inherit the shop's lunch break, so none is configured per barber.
    for shop in shops:
        for day in DAYS:
            business_hour, _ = BusinessHour.objects.update_or_create(
                shop=shop,
                day_of_week=day,
                defaults={"open_time": time(9, 0), "close_time": time(21, 0), "is_closed": False},
            )
            BusinessHourBreak.objects.update_or_create(
                business_hour=business_hour,
                defaults={"start_time": time(13, 0), "end_time": time(14, 0)},
            )

    for barber in barbers:
        for day in DAYS:
            BarberShift.objects.update_or_create(
                barber=barber,
                day_of_week=day,
                shift_date=None,
                defaults={"start_time": time(9, 0), "end_time": time(21, 0), "is_active": True},
            )

    category_data = {
        "Haircuts": [("Classic Haircut", "A clean, timeless cut", Decimal("500.00"), 45), ("Skin Fade", "Sharp modern fade", Decimal("700.00"), 60)],
        "Beard": [("Beard Trim", "Shape and finish", Decimal("300.00"), 30), ("Hair and Beard Combo", "Complete grooming service", Decimal("900.00"), 75)],
    }
    services_by_shop = {}
    for shop in shops:
        shop_barbers = [barber.user for barber in barbers if barber.shop_id == shop.id]
        services_by_shop[shop.id] = []
        for category_name, service_data in category_data.items():
            category, _ = ServiceCategory.objects.update_or_create(shop=shop, name=category_name, defaults={"is_active": True})
            for name, description, price, duration in service_data:
                service, _ = Service.objects.update_or_create(
                    shop=shop,
                    name=name,
                    defaults={"category": category, "description": description, "price": price, "duration_minutes": duration, "is_active": True},
                )
                service.barbers.set(shop_barbers)
                services_by_shop[shop.id].append(service)

    shop = shops[0]
    services = services_by_shop[shop.id]

    completed_booking, _ = Booking.objects.update_or_create(
        booking_code="BB-DEMO-001",
        defaults={
            "customer": customers[0], "shop": shop, "total_amount": services[0].price,
            "payment_method": "card", "payment_status": "paid", "status": "completed",
        },
    )
    Appointment.objects.update_or_create(
        booking=completed_booking,
        service=services[0],
        defaults={"barber": barbers[0], "appointment_date": today - timedelta(days=2), "start_time": time(11, 0), "end_time": time(11, 45), "price": services[0].price, "status": "completed"},
    )
    ShopReview.objects.update_or_create(
        booking=completed_booking,
        defaults={"shop": shop, "customer": customers[0], "rating": 5, "comment": "Great service and a friendly team."},
    )

    upcoming_booking, _ = Booking.objects.update_or_create(
        booking_code="BB-DEMO-002",
        defaults={
            "customer": customers[1], "shop": shop, "total_amount": services[1].price,
            "payment_method": "cash", "payment_status": "pending", "status": "confirmed",
        },
    )
    Appointment.objects.update_or_create(
        booking=upcoming_booking,
        service=services[1],
        defaults={"barber": barbers[1], "appointment_date": today + timedelta(days=2), "start_time": time(15, 0), "end_time": time(16, 0), "price": services[1].price, "status": "scheduled"},
    )

    print("Demo data is ready.")
    print(f"Super admin: {SUPER_ADMIN_EMAIL} / {SUPER_ADMIN_PASSWORD}")
    print(f"Admin: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    for email, password, _name in MANAGER_ACCOUNTS:
        print(f"Manager: {email} / {password}")
    for email, password, _name, _specialty, _shop_index in STAFF_ACCOUNTS:
        print(f"Staff: {email} / {password}")
    for email, password, _name in CUSTOMER_ACCOUNTS:
        print(f"User: {email} / {password}")
    print(f"Shops: {len(shops)} | Services per shop: {len(services)} | Barbers: {len(barbers)} | Customers: {len(customers)}")


if __name__ == "__main__":
    populate()