from datetime import date
from django.db.models import Sum, Avg, Count
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.core.responses import success_response
from apps.barber.models import Barber
from apps.barber.serializers import BarberSerializer
from apps.service.models import Service
from apps.schedule.models import BarberShift, BarberTimeOff
from apps.booking.models import Booking, ShopReview

class StaffProfileAPIView(APIView):
    """GET: Get logged in staff/barber profile summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        serializer = BarberSerializer(barber, context={"request": request})
        return success_response(details="Staff profile retrieved", code="STAFF_PROFILE", data=serializer.data)


class StaffServicesAPIView(APIView):
    """GET: List all services offered by the logged-in staff."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        services = Service.objects.filter(barbers=request.user)
        
        # Manually construct response to match UI (Name, duration, price)
        data = [
            {
                "id": svc.id,
                "name": svc.name,
                "duration_minutes": svc.duration_minutes,
                "price": svc.price
            } for svc in services
        ]
        return success_response(details="Staff services retrieved", code="STAFF_SERVICES", data=data)


class StaffScheduleAPIView(APIView):
    """GET: Get working days and hours for logged-in staff."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        shifts = BarberShift.objects.filter(barber=barber)
        
        data = []
        for shift in shifts:
            data.append({
                "id": shift.id,
                "day_of_week": shift.day_of_week,
                "start_time": shift.start_time.strftime("%I:%M %p").lower(),
                "end_time": shift.end_time.strftime("%I:%M %p").lower(),
                "is_active": shift.is_active
            })
        return success_response(details="Staff schedule retrieved", code="STAFF_SCHEDULE", data=data)


class StaffTimeOffAPIView(APIView):
    """GET: Get break schedule / time off for logged-in staff."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        time_offs = BarberTimeOff.objects.filter(barber=barber)
        
        data = []
        for to in time_offs:
            data.append({
                "id": to.id,
                "reason": to.reason,
                "start_date": to.start_date.strftime("%d %b"),
                "end_date": to.end_date.strftime("%d %b") if to.end_date else None,
                "status": to.status
            })
        return success_response(details="Staff time off retrieved", code="STAFF_TIME_OFF", data=data)


class StaffReviewAPIView(APIView):
    """GET: Get reviews for the logged-in staff."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        reviews = ShopReview.objects.filter(booking__appointments__barber=barber).distinct()

        stats = reviews.aggregate(average=Avg("rating"), total_reviews=Count("id"))
        
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        rating_counts = reviews.values("rating").annotate(count=Count("id"))
        for rc in rating_counts:
            if rc["rating"] in distribution:
                distribution[rc["rating"]] = rc["count"]

        reviews_data = []
        for review in reviews:
            reviews_data.append({
                "id": review.id,
                "rating": review.rating,
                "comment": review.comment,
                "customer_name": review.customer.full_name or review.customer.username,
                "customer_avatar": request.build_absolute_uri(review.customer.image.url) if review.customer.image else None,
                "date": review.created_at.strftime("%d %b %Y"),
            })

        data = {
            "summary": {
                "average_rating": round(stats["average"] or 0, 1),
                "total_reviews": stats["total_reviews"],
                "distribution": distribution,
            },
            "reviews": reviews_data
        }

        return success_response(details="Staff reviews retrieved", code="STAFF_REVIEWS", data=data)


class StaffReportAPIView(APIView):
    """GET: Get total bookings and revenue report for logged-in staff."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        
        # Month filter could be added from query params
        # Get all appointments completed by this barber
        from apps.booking.models import Appointment
        appointments = Appointment.objects.filter(barber=barber, status="completed")
        
        total_bookings = appointments.count()
        total_revenue = appointments.aggregate(total=Sum("price"))["total"] or 0.0
        
        appt_data = []
        for appt in appointments.order_by("-appointment_date"):
            appt_data.append({
                "id": appt.id,
                "customer_name": appt.booking.customer.full_name or appt.booking.customer.username,
                "service_name": appt.service.name,
                "price": float(appt.price),
                "date": appt.appointment_date.strftime("%d %b %Y")
            })

        data = {
            "total_bookings": total_bookings,
            "total_revenue": float(total_revenue),
            "history": appt_data
        }
        return success_response(details="Staff reports retrieved", code="STAFF_REPORTS", data=data)


class StaffShopAPIView(APIView):
    """GET: Get details of the shop this staff member is assigned to."""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        barber = get_object_or_404(Barber, user=request.user)
        shop = barber.shop
        if not shop:
            return success_response(details="No shop assigned", code="NO_SHOP", data={})
            
        from apps.shop.serializers import ShopSerializer
        serializer = ShopSerializer(shop, context={"request": request})
        return success_response(details="Staff shop retrieved", code="STAFF_SHOP", data=serializer.data)
