import sys

# 1. Update Shop Creation
shop_filepath = 'apps/shop/views.py'
with open(shop_filepath, 'r') as f:
    shop_content = f.read()

shop_old_block = """    def post(self, request, *args, **kwargs):
        serializer = ShopSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        # Note: we explicitly set owner to request.user during save
        serializer.save(owner=request.user)
        return success_response(
            details="Shop created successfully.",
            code="SHOP_CREATED",
            data=serializer.data,
        )"""

shop_new_block = """    def post(self, request, *args, **kwargs):
        serializer = ShopSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        # Note: we explicitly set owner to request.user during save
        shop = serializer.save(owner=request.user)
        
        # Auto-create default business hours for 7 days
        from apps.shop.models import BusinessHour
        for day in ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]:
            BusinessHour.objects.get_or_create(
                shop=shop, 
                day_of_week=day, 
                defaults={"open_time": "09:00:00", "close_time": "17:00:00"}
            )
            
        return success_response(
            details="Shop created successfully.",
            code="SHOP_CREATED",
            data=serializer.data,
        )"""

if shop_old_block in shop_content:
    shop_content = shop_content.replace(shop_old_block, shop_new_block)
    with open(shop_filepath, 'w') as f:
        f.write(shop_content)
    print("Shop updated")
else:
    print("Shop block not found")

# 2. Update Barber Creation
barber_filepath = 'apps/barber/views.py'
with open(barber_filepath, 'r') as f:
    barber_content = f.read()

barber_old_block = """    def post(self, request, *args, **kwargs):
        serializer = BarberSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            details="Barber created successfully.",
            code="BARBER_CREATED",
            data=serializer.data,
        )"""

barber_new_block = """    def post(self, request, *args, **kwargs):
        serializer = BarberSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        barber = serializer.save()
        
        # Auto-create 7-day default shifts using shop business hours
        from apps.shop.models import BusinessHour
        from apps.schedule.models import BarberShift
        import datetime
        
        shop_hours = {}
        if barber.shop_id:
            shop_hours = {
                bh.day_of_week: bh 
                for bh in BusinessHour.objects.filter(shop_id=barber.shop_id)
            }
            
        days_of_week = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        new_shifts = []
        for day in days_of_week:
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
                    barber=barber,
                    day_of_week=day,
                    start_time=default_start,
                    end_time=default_end,
                    is_active=False if (default_start == default_end) else True
                )
            )
        BarberShift.objects.bulk_create(new_shifts)

        return success_response(
            details="Barber created successfully.",
            code="BARBER_CREATED",
            data=serializer.data,
        )"""

if barber_old_block in barber_content:
    barber_content = barber_content.replace(barber_old_block, barber_new_block)
    with open(barber_filepath, 'w') as f:
        f.write(barber_content)
    print("Barber updated")
else:
    print("Barber block not found")
