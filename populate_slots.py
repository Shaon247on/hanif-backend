import os
import django
from datetime import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from apps.shop.models import Shop, BusinessHour
from apps.barber.models import Barber
from apps.schedule.models import BarberShift, BarberBreak

def populate():
    # 1. Shop Business Hours
    shop = Shop.objects.first()
    if not shop:
        print("No shop found!")
        return

    days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    for day in days:
        BusinessHour.objects.get_or_create(
            shop=shop,
            day_of_week=day,
            defaults={
                "open_time": time(9, 0),
                "close_time": time(21, 0),
                "is_closed": False
            }
        )
    print(f"Created/Updated business hours for shop {shop.name}")

    # 2. Barber Shifts & Breaks
    barbers = Barber.objects.all()
    for barber in barbers:
        for day in days:
            # Shift from 9 AM to 9 PM
            BarberShift.objects.get_or_create(
                barber=barber,
                day_of_week=day,
                defaults={
                    "start_time": time(9, 0),
                    "end_time": time(21, 0),
                    "is_active": True
                }
            )
            # Break from 1 PM to 2 PM
            BarberBreak.objects.get_or_create(
                barber=barber,
                day_of_week=day,
                defaults={
                    "start_time": time(13, 0),
                    "end_time": time(14, 0),
                    "title": "Lunch Break",
                    "is_active": True
                }
            )
        print(f"Created shifts and breaks for barber {barber}")

if __name__ == "__main__":
    populate()
