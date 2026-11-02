import logging
import secrets

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.views import APIView

from apps.barber.models import Barber
from apps.core.access import require_access_shop, require_manage_shop
from apps.core.permissions import IsShopStaff
from apps.core.responses import success_response
from apps.schedule.services import ScheduleService
from apps.service.models import Service
from apps.shop.models import Shop
from apps.user.enums import UserRole
from apps.user.models import User

logger = logging.getLogger(__name__)


class AdminStaffListCreateAPIView(APIView):
    permission_classes = [IsShopStaff]
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_access_shop(request.user, shop.id)
        barbers = Barber.objects.filter(shop=shop).select_related("user")

        data = []
        for b in barbers:
            data.append(
                {
                    "id": b.id,
                    "user_id": b.user.id,
                    "name": b.user.full_name or b.user.username,
                    "email": b.user.email,
                    "phone": b.user.phone,
                    "role": b.user.role,
                    "position": b.specialty,
                    "avatar": request.build_absolute_uri(b.user.image.url) if b.user.image else None,
                }
            )

        return success_response(details="Staff retrieved", code="STAFF_RETRIEVED", data=data)

    def post(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)

        email = request.data.get("email")
        name = request.data.get("name")
        phone = request.data.get("phone", "")
        position = request.data.get("position", "")
        role = UserRole.BARBER.value  # Managers are created through /shops/managers/ by admins only
        services = (
            request.data.getlist("services") if hasattr(request.data, "getlist") else request.data.get("services", [])
        )
        avatar = request.FILES.get("avatar")

        if not email:
            return success_response(details="Email is required", code="EMAIL_REQUIRED", data={})

        if User.objects.filter(email=email).exists():
            return success_response(details="User with this email already exists", code="USER_EXISTS", data={})

        generated_password = secrets.token_urlsafe(12)

        with transaction.atomic():
            user = User.objects.create_user(
                username=secrets.token_urlsafe(12),
                email=email,
                password=generated_password,
                full_name=name,
                phone=phone,
                role=role,
            )
            if avatar:
                user.image = avatar
            user.set_unique_username()
            user.save()
            actual_username = user.username

            barber = Barber.objects.create(user=user, shop=shop, specialty=position)
            ScheduleService.create_default_shifts(barber)

            if services:
                # Expecting service IDs
                if isinstance(services, str):
                    services = [services]
                service_objs = Service.objects.filter(id__in=services, shop=shop)
                for svc in service_objs:
                    svc.barbers.add(user)

        # Send Email to the new staff
        try:
            subject = f"Welcome to {shop.name}!"
            message = (
                f"Hello {name or actual_username},\n\n"
                f"Your account has been created successfully.\n"
                f"Login Email: {email}\n"
                f"Username: {actual_username}\n"
                f"Temporary Password: {generated_password}\n\n"
                f"Please login and change your password."
            )
            from_email = getattr(settings, "EMAIL_HOST_USER", "") or getattr(
                settings, "DEFAULT_FROM_EMAIL", "noreply@barberbay.com"
            )
            send_mail(subject, message, from_email, [email], fail_silently=False)
        except Exception:
            logger.exception("Failed to send credentials email to staff %s", email)

        response_data = {
            "id": barber.id,
            "user_id": user.id,
            "username": actual_username,
            "email": email,
            "password": generated_password,
            "role": role,
            "position": position
        }

        return success_response(
            details="Staff member created and credentials emailed successfully",
            code="STAFF_CREATED",
            data=response_data
        )


class AdminStaffDetailAPIView(APIView):
    permission_classes = [IsShopStaff]
    parser_classes = [MultiPartParser, JSONParser]

    def patch(self, request, shop_id, pk, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        barber = get_object_or_404(Barber, pk=pk, shop_id=shop_id)
        user = barber.user

        name = request.data.get("name")
        phone = request.data.get("phone")
        position = request.data.get("position")
        avatar = request.FILES.get("avatar")
        services = (
            request.data.getlist("services") if hasattr(request.data, "getlist") else request.data.get("services")
        )

        if name is not None:
            user.full_name = name
        if phone is not None:
            user.phone = phone
        if avatar is not None:
            user.image = avatar
        user.save()

        if position is not None:
            barber.specialty = position
            barber.save()

        if services is not None:
            if isinstance(services, str):
                services = [services]

            # Clear old services for this barber and shop
            old_services = Service.objects.filter(barbers=user, shop_id=shop_id)
            for svc in old_services:
                svc.barbers.remove(user)

            # Add new
            new_services = Service.objects.filter(id__in=services, shop_id=shop_id)
            for svc in new_services:
                svc.barbers.add(user)

        return success_response(details="Staff member updated", code="STAFF_UPDATED", data={})

    def delete(self, request, shop_id, pk, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        barber = get_object_or_404(Barber, pk=pk, shop_id=shop_id)
        user = barber.user
        barber.delete()
        # Optionally, deactivate the user instead of deleting
        user.is_active = False
        user.save()
        return success_response(details="Staff member removed", code="STAFF_DELETED", data={})
