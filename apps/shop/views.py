import os

import requests
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.core.access import require_manage_shop
from apps.core.responses import error_response, success_response
from apps.core.permissions import IsAdmin, IsGlobalAdmin
from apps.user.enums import UserRole

from .models import Shop, ShopGallery
from .serializers import ImageSerializer, ShopDetailsSerializer, ShopListSerializer, ShopSerializer


class SelectActiveShopAPIView(APIView):
    """Persist the shop currently selected by the authenticated user."""

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        from apps.user.serializers import get_user_shops

        shop = get_object_or_404(Shop, pk=request.data.get("shop"))
        accessible_shop_ids = {item["id"] for item in get_user_shops(request.user, context={"request": request})}
        if shop.id not in accessible_shop_ids:
            return success_response(
                details="You do not have access to this shop.",
                code="SHOP_ACCESS_DENIED",
                status_code=status.HTTP_403_FORBIDDEN,
                data={},
            )

        request.user.active_shop = shop
        request.user.save(update_fields=["active_shop"])
        from .serializers import ShopBasicSerializer

        return success_response(
            details="Active shop selected successfully.",
            code="ACTIVE_SHOP_SELECTED",
            data={"active_shop": ShopBasicSerializer(shop, context={"request": request}).data},
        )


class ShopGoogleReviewsAPIView(APIView):
    """Fetch Google reviews or return the link used to create one."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk, *args, **kwargs):
        """Return the shop's Google review URL for the client to open."""
        shop = get_object_or_404(Shop, pk=pk)

        if not shop.google_review_link:
            return success_response(
                details="Google review link is not configured for this shop.",
                code="MISSING_REVIEW_LINK",
                status_code=status.HTTP_400_BAD_REQUEST,
                data={},
            )

        return success_response(
            details="Google review link retrieved successfully.",
            code="GOOGLE_REVIEW_CREATE_LINK",
            data={"review_url": shop.google_review_link},
        )

    def get(self, request, pk, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=pk)

        if not shop.google_place_id:
            return success_response(
                details="Google Place ID not configured for this shop.", code="MISSING_PLACE_ID", data={}
            )

        api_key = getattr(settings, "GOOGLE_MAPS_API_KEY", os.environ.get("GOOGLE_MAPS_API_KEY"))
        if not api_key:
            return success_response(
                details="Google Maps API Key is missing in backend.", code="MISSING_API_KEY", data={}
            )

        url = "https://maps.googleapis.com/maps/api/place/details/json"
        params = {
            "place_id": shop.google_place_id,
            "fields": "rating,user_ratings_total,reviews",
            "key": api_key,
            "language": "en",
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                return success_response(
                    details=f"Google API Error: {data.get('status')}", code="GOOGLE_API_ERROR", data={}
                )

            result = data.get("result", {})
            return success_response(
                details="Google reviews fetched successfully.",
                code="GOOGLE_REVIEWS_FETCHED",
                data={
                    "rating": result.get("rating", 0.0),
                    "total_ratings": result.get("user_ratings_total", 0),
                    "reviews": result.get("reviews", []),
                },
            )
        except Exception as e:
            return success_response(details=f"Failed to fetch from Google: {str(e)}", code="FETCH_FAILED", data={})


class ShopListCreateAPIView(APIView):
    """
    GET: List all shops.
    POST: Create a new shop.
    """

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsGlobalAdmin()]

    def get(self, request, *args, **kwargs):
        shops = Shop.objects.all()
        serializer = ShopListSerializer(shops, many=True, context={"request": request})
        return success_response(
            details="Shop list retrieved successfully.",
            code="SHOP_LIST_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
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
        )


class ShopDetailsUpdateDeleteAPIView(APIView):
    """
    GET: Retrieve shop details.
    PUT/PATCH: Update shop details.
    DELETE: Delete a shop.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        if self.request.method == "DELETE":
            return [IsGlobalAdmin()]
        return [IsAdmin()]

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, pk):
        return get_object_or_404(Shop, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        shop = self.get_object(pk)
        serializer = ShopDetailsSerializer(shop, context={"request": request})
        return success_response(
            details="Shop details retrieved successfully.",
            code="SHOP_DETAILS_RETRIEVED",
            data=serializer.data,
        )

    def put(self, request, pk, *args, **kwargs):
        shop = self.get_object(pk)
        require_manage_shop(request.user, shop.id)
        serializer = ShopDetailsSerializer(shop, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated_shop = serializer.save()
        return success_response(
            details="Shop updated successfully.",
            code="SHOP_UPDATED",
            data=ShopDetailsSerializer(updated_shop, context={"request": request}).data,
        )

    def delete(self, request, pk, *args, **kwargs):
        shop = self.get_object(pk)
        shop.delete()
        return success_response(
            details="Shop deleted successfully.",
            code="SHOP_DELETED",
            data={},
        )


class ShopGalleryListCreateAPIView(APIView):
    """
    GET: List all gallery images (optionally filter by shop).
    POST: Add one or more images to the shop gallery.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdmin()]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop")
        galleries = ShopGallery.objects.filter(shop_id=shop_id) if shop_id else ShopGallery.objects.all()
        serializer = ImageSerializer(galleries, many=True, context={"request": request})
        return success_response(
            details="Shop gallery retrieved successfully.",
            code="SHOP_GALLERY_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
        shop_id = request.data.get("shop")
        if not shop_id:
            return success_response(
                details="Shop ID is required.",
                code="SHOP_ID_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST if hasattr(status, "HTTP_400_BAD_REQUEST") else 400,
            )

        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)

        # Get list of files uploaded. Support both 'images' and 'image' keys
        images = request.FILES.getlist("images")
        if not images and "image" in request.FILES:
            images = [request.FILES["image"]]

        if not images:
            return success_response(
                details="No images provided. Please provide images using the 'images' field.",
                code="IMAGES_REQUIRED",
                status_code=status.HTTP_400_BAD_REQUEST if hasattr(status, "HTTP_400_BAD_REQUEST") else 400,
            )

        # Parse optional display_order list or single value
        display_orders = request.data.getlist("display_order") if hasattr(request.data, "getlist") else []
        if not display_orders and "display_order" in request.data:
            display_orders = [request.data["display_order"]]

        created_galleries = []
        for i, img_file in enumerate(images):
            # Determine display order for this image if specified
            order = 0
            if i < len(display_orders):
                try:
                    order = int(display_orders[i])
                except (ValueError, TypeError):
                    order = 0

            gallery = ShopGallery.objects.create(
                shop=shop,
                image=img_file,
                display_order=order,
            )
            created_galleries.append(gallery)

        serializer = ImageSerializer(created_galleries, many=True, context={"request": request})
        return success_response(
            details="Shop gallery images created successfully.",
            code="SHOP_GALLERY_CREATED",
            data=serializer.data,
        )


class ShopGalleryDetailsUpdateDeleteAPIView(APIView):
    """
    GET: Retrieve a single gallery image.
    PUT/PATCH: Update gallery image (e.g., display_order, image).
    DELETE: Delete a gallery image.
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdmin()]

    def get_object(self, pk):
        return get_object_or_404(ShopGallery, pk=pk)

    def get(self, request, pk, *args, **kwargs):
        gallery = self.get_object(pk)
        serializer = ImageSerializer(gallery)
        return success_response(
            details="Shop gallery image retrieved successfully.",
            code="SHOP_GALLERY_DETAILS_RETRIEVED",
            data=serializer.data,
        )

    def put(self, request, pk, *args, **kwargs):
        gallery = self.get_object(pk)
        require_manage_shop(request.user, gallery.shop_id)
        data = request.data.copy()
        data["shop"] = gallery.shop_id  # Ensure shop is not changed
        serializer = ImageSerializer(gallery, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        updated_gallery = serializer.save()
        return success_response(
            details="Shop gallery image updated successfully.",
            code="SHOP_GALLERY_UPDATED",
            data=ImageSerializer(updated_gallery).data,
        )

    def delete(self, request, pk, *args, **kwargs):
        gallery = self.get_object(pk)
        require_manage_shop(request.user, gallery.shop_id)
        gallery.delete()
        return success_response(
            details="Shop gallery image deleted successfully.",
            code="SHOP_GALLERY_DELETED",
            data={},
        )


class ShopPaymentSettingsAPIView(APIView):
    """
    GET: Check if payment is enabled (publicly accessible during checkout).
    PATCH: Toggle payment settings (admin only).
    """

    def get_permissions(self):
        from rest_framework.permissions import AllowAny, IsAuthenticated

        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAdmin()]

    def get(self, request, pk, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=pk)
        return success_response(
            details="Payment settings retrieved.",
            code="PAYMENT_SETTINGS",
            data={
                "shop_id": shop.id,
                "payment_gateway_enabled": shop.payment_gateway_enabled,
                "supported_methods": ["stripe"],
            },
        )

    def patch(self, request, pk, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=pk)
        require_manage_shop(request.user, shop.id)
        is_enabled = request.data.get("payment_gateway_enabled")

        if is_enabled is not None:
            # handle string 'true' / 'false' if passed from form-data
            if isinstance(is_enabled, str):
                is_enabled = is_enabled.lower() == "true"
            shop.payment_gateway_enabled = is_enabled
            shop.save()

        return success_response(
            details="Payment settings updated.",
            code="PAYMENT_SETTINGS_UPDATED",
            data={"shop_id": shop.id, "payment_gateway_enabled": shop.payment_gateway_enabled},
        )


def _serialize_manager(manager):
    return {
        "id": manager.id,
        "email": manager.email,
        "full_name": manager.full_name,
        "phone": manager.phone,
        "is_active": manager.is_active,
        "role": manager.role,
        "shops": [{"id": s.id, "name": s.name} for s in manager.managed_shops.all()],
    }


def _resolve_manager_shop(request):
    """A manager runs exactly one shop; shop_ids stays a list for API compatibility."""
    shop_ids = request.data.get("shop_ids")
    if not isinstance(shop_ids, list) or len(shop_ids) != 1:
        raise ValidationError({"shop_ids": "A manager must be assigned to exactly one shop."})
    shop = Shop.objects.filter(pk=shop_ids[0]).first()
    if not shop:
        raise ValidationError({"shop_ids": "Invalid shop ID."})
    return shop


class ManagerListCreateAPIView(APIView):
    """Admins create managers and assign each one to a single shop."""

    permission_classes = [IsGlobalAdmin]

    def get(self, request, *args, **kwargs):
        from apps.user.models import User

        shop_id = request.query_params.get("shop_id")
        if shop_id:
            managers = get_object_or_404(Shop, pk=shop_id).managers.all()
        else:
            managers = User.objects.filter(role=UserRole.MANAGER)

        return success_response(
            details="Managers retrieved.",
            code="MANAGERS_RETRIEVED",
            data=[_serialize_manager(manager) for manager in managers],
        )

    def post(self, request, *args, **kwargs):
        from django.contrib.auth.hashers import make_password

        from apps.notification.utils import send_push_and_email
        from apps.user.models import User

        email = request.data.get("email")
        password = request.data.get("password")
        full_name = request.data.get("full_name", "")
        phone = request.data.get("phone", "")

        if not email or not password:
            return error_response(details="shop_ids (list), email, and password are required.", code="MISSING_PARAMS")
        shop = _resolve_manager_shop(request)

        user = User.objects.filter(email=email).first()
        is_new = False
        if not user:
            user = User(email=email, full_name=full_name, phone=phone, role=UserRole.MANAGER, is_active=True, status=1)
            user.set_unique_username()
            user.password = make_password(password)
            user.save()
            is_new = True
        else:
            if user.role not in (UserRole.USER, UserRole.MANAGER):
                return error_response(
                    details="This account already has a staff or admin role.", code="INVALID_MANAGER_ACCOUNT"
                )
            if user.managed_shops.exclude(pk=shop.id).exists():
                return error_response(
                    details="This manager is already assigned to another shop.", code="MANAGER_ALREADY_ASSIGNED"
                )
            user.role = UserRole.MANAGER
            user.is_active = True
            user.status = 1
            user.save(update_fields=["role", "is_active", "status"])

        shop.managers.add(user)

        if is_new:
            send_push_and_email(
                user=user,
                title="Welcome as a Manager!",
                message=f"You have been added as a manager. Your login email is {email} and your password is: {password}",
                notif_type="system",
                send_email=True,
            )

        return success_response(
            details="Manager created and assigned successfully.",
            code="MANAGER_CREATED",
            data={
                "manager_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "assigned_shops": [{"id": shop.id, "name": shop.name}],
            },
        )


class ManagerDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsGlobalAdmin]

    def get_object(self, pk):
        from apps.user.models import User

        return get_object_or_404(User, pk=pk, role=UserRole.MANAGER)

    def get(self, request, pk, *args, **kwargs):
        return success_response(
            details="Manager retrieved.", code="MANAGER_RETRIEVED", data=_serialize_manager(self.get_object(pk))
        )

    def patch(self, request, pk, *args, **kwargs):
        manager = self.get_object(pk)

        if "full_name" in request.data:
            manager.full_name = request.data["full_name"]
        if "phone" in request.data:
            manager.phone = request.data["phone"]
        if "is_active" in request.data:
            manager.is_active = request.data["is_active"]
            manager.status = 1 if manager.is_active else 0

        if "password" in request.data and request.data["password"]:
            from django.contrib.auth.hashers import make_password

            manager.password = make_password(request.data["password"])

        shop = _resolve_manager_shop(request) if "shop_ids" in request.data else None
        manager.save()
        if shop:
            manager.managed_shops.set([shop])

        return success_response(details="Manager updated.", code="MANAGER_UPDATED", data=_serialize_manager(manager))

    def put(self, request, pk, *args, **kwargs):
        return self.patch(request, pk, *args, **kwargs)

    def delete(self, request, pk, *args, **kwargs):
        self.get_object(pk).delete()
        return success_response(details="Manager deleted/removed successfully.", code="MANAGER_DELETED", data={})
