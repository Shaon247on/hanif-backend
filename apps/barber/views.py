import logging

from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.core.access import can_access_shop, require_access_shop, require_manage_shop
from apps.core.permissions import IsAdmin
from apps.core.responses import success_response
from apps.schedule.services import ScheduleService

from .models import Barber
from .serializers import BarberListSerializer, BarberSerializer, BarberShopOptionSerializer

logger = logging.getLogger(__name__)


class ShopBarberOptionsAPIView(APIView):
    """Return only barber IDs and names for a selected shop."""

    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop")
        if not shop_id:
            return success_response(
                details="Shop ID is required.",
                code="SHOP_ID_REQUIRED",
                status_code=400,
                data={},
            )

        barbers = Barber.objects.filter(shop_id=shop_id).select_related("user").order_by("user__full_name")
        return success_response(
            details="Shop barber options retrieved successfully.",
            code="SHOP_BARBER_OPTIONS_RETRIEVED",
            data=BarberShopOptionSerializer(barbers, many=True).data,
        )


class BarberListCreateAPIView(APIView):
    """
    GET: List all barbers (optionally filter by shop).
    POST: Create a new barber.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdmin()]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop")
        barbers = Barber.objects.filter(shop_id=shop_id)
        # The list is public for customers; contact details stay with the shop's own staff.
        context = {"request": request, "include_contact_details": can_access_shop(request.user, shop_id)}
        serializer = BarberListSerializer(barbers, many=True, context=context)
        return success_response(
            details="Barber list retrieved successfully.",
            code="BARBER_LIST_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
        serializer = BarberSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        require_manage_shop(request.user, serializer.validated_data["shop"].id)
        barber = serializer.save()

        generated_password = getattr(barber, "generated_password", None)
        if generated_password:
            try:
                user = barber.user
                project_name = getattr(settings, "PROJECT_NAME", "BarberBay")
                message = (
                    f"Hello {user.full_name or user.username},\n\n"
                    "Your barber account has been created successfully.\n"
                    f"Login Email: {user.email}\n"
                    f"Temporary Password: {generated_password}\n\n"
                    "Please login and change your password."
                )
                html_message = render_to_string(
                    "emails/barber_credentials.html",
                    {
                        "display_name": user.full_name or user.username,
                        "email": user.email,
                        "password": generated_password,
                        "project_name": project_name,
                        "year": timezone.now().year,
                    },
                )
                send_mail(
                    subject=f"Welcome to {barber.shop.name}!",
                    message=message,
                    from_email=getattr(settings, "EMAIL_HOST_USER", "")
                    or getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@barberbay.com"),
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
            except Exception:
                logger.exception("Failed to send credentials email to barber %s", barber.user.email)

        ScheduleService.create_default_shifts(barber)

        return success_response(
            details="Barber created successfully.",
            code="BARBER_CREATED",
            data=serializer.data,
        )


class BarberDetailsUpdateDeleteAPIView(APIView):
    """
    GET: Retrieve barber details.
    PUT/PATCH: Update barber details.
    DELETE: Delete a barber.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        return get_object_or_404(Barber, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        barber = self.get_object(pk)
        require_access_shop(request.user, barber.shop_id)
        serializer = BarberSerializer(barber, context={"request": request})
        return success_response(
            details="Barber details retrieved successfully.",
            code="BARBER_DETAILS_RETRIEVED",
            data=serializer.data,
        )

    def put(self, request, pk, *args, **kwargs):
        barber = self.get_object(pk)
        require_manage_shop(request.user, barber.shop_id)
        serializer = BarberSerializer(barber, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if "shop" in serializer.validated_data:
            require_manage_shop(request.user, serializer.validated_data["shop"].id)
        updated_barber = serializer.save()
        return success_response(
            details="Barber updated successfully.",
            code="BARBER_UPDATED",
            data=BarberSerializer(updated_barber, context={"request": request}).data,
        )

    def delete(self, request, pk, *args, **kwargs):
        barber = self.get_object(pk)
        require_manage_shop(request.user, barber.shop_id)
        barber.delete()
        return success_response(
            details="Barber deleted successfully.",
            code="BARBER_DELETED",
            data={},
        )
