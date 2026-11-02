import sys

filepath = 'apps/schedule/views.py'
with open(filepath, 'r') as f:
    content = f.read()

old_block = """            if missing_days:
                new_shifts = []
                for day in missing_days:
                    new_shifts.append(
                        BarberShift(
                            barber_id=barber_id,
                            day_of_week=day,
                            start_time=datetime.time(0, 0),
                            end_time=datetime.time(0, 0),
                            is_active=True
                        )
                    )
                BarberShift.objects.bulk_create(new_shifts)"""

new_block = """            if missing_days:
                from apps.schedule.models import BusinessHour
                from apps.barber.models import Barber
                barber_obj = Barber.objects.filter(id=barber_id).first()
                if barber_obj and barber_obj.shop_id:
                    shop_hours = {
                        bh.day_of_week: bh 
                        for bh in BusinessHour.objects.filter(shop_id=barber_obj.shop_id)
                    }
                else:
                    shop_hours = {}

                new_shifts = []
                for day in missing_days:
                    # Default to 09:00 - 17:00 if shop hours don't exist
                    default_start = datetime.time(9, 0)
                    default_end = datetime.time(17, 0)
                    
                    if day in shop_hours:
                        bh = shop_hours[day]
                        if bh.open_time and bh.close_time:
                            default_start = bh.open_time
                            default_end = bh.close_time
                        elif bh.is_closed:
                            default_start = datetime.time(0, 0)
                            default_end = datetime.time(0, 0)

                    new_shifts.append(
                        BarberShift(
                            barber_id=barber_id,
                            day_of_week=day,
                            start_time=default_start,
                            end_time=default_end,
                            is_active=False if (default_start == default_end) else True
                        )
                    )
                BarberShift.objects.bulk_create(new_shifts)"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Done")
else:
    print("Block not found!")
