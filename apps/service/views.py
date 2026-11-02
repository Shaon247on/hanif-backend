from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from apps.barber.models import Barber
from apps.core.access import require_manage_shop
from apps.core.responses import success_response
from apps.service.models import Service, ServiceCategory
from apps.service.serializers import ServiceCategorySerializer, ServiceListSerializer, ServiceSerializer


class ServiceCategoryCreateListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop")
        categories = ServiceCategory.objects.all()
        if shop_id:
            categories = categories.filter(shop_id=shop_id)
        serializer = ServiceCategorySerializer(categories, many=True)
        return success_response(
            details="Service categories retrieved successfully.",
            code="SERVICE_CATEGORIES_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
        serializer = ServiceCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_manage_shop(request.user, serializer.validated_data["shop"].id)
        category = serializer.save()
        return success_response(
            details="Service category created successfully.",
            code="SERVICE_CATEGORY_CREATED",
            data=ServiceCategorySerializer(category).data,
        )


class ServiceCategoryDeleteAPIView(APIView):
    def delete(self, request, *args, **kwargs):
        category = get_object_or_404(ServiceCategory, pk=kwargs["pk"])
        require_manage_shop(request.user, category.shop_id)
        category.delete()
        return success_response(
            details="Service category deleted successfully.",
            code="SERVICE_CATEGORY_DELETED",
            data={},
        )


class ServiceCreateListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        barber_id = request.query_params.get("barber")
        shop_id = request.query_params.get("shop")

        services = Service.objects.select_related("category").prefetch_related("barbers")

        if shop_id:
            if str(shop_id).isdigit():
                services = services.filter(shop_id=shop_id)
            else:
                services = services.none()

        if barber_id:
            try:
                barber = Barber.objects.get(id=barber_id)
                services = services.filter(barbers=barber.user).distinct()
            except (ValueError, Barber.DoesNotExist):
                services = services.none()

        serializer = ServiceListSerializer(services, many=True)
        return success_response(
            details="Services retrieved successfully.",
            code="SERVICES_RETRIEVED",
            data=serializer.data,
        )

    def post(self, request, *args, **kwargs):
        serializer = ServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        require_manage_shop(request.user, serializer.validated_data["shop"].id)
        service = serializer.save()
        return success_response(
            details="Service created successfully.",
            code="SERVICE_CREATED",
            data=ServiceSerializer(service).data,
        )


class ServiceUpdateDeleteAPIView(APIView):
    def get(self, request, *args, **kwargs):
        service = get_object_or_404(Service, pk=kwargs["pk"])
        serializer = ServiceSerializer(service)
        return success_response(
            details="Service retrieved successfully.",
            code="SERVICE_RETRIEVED",
            data=serializer.data,
        )

    def patch(self, request, *args, **kwargs):
        service = get_object_or_404(Service, pk=kwargs["pk"])
        require_manage_shop(request.user, service.shop_id)
        serializer = ServiceSerializer(service, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        service = serializer.save()
        return success_response(
            details="Service updated successfully.",
            code="SERVICE_UPDATED",
            data=ServiceSerializer(service).data,
        )

    def delete(self, request, *args, **kwargs):
        service = get_object_or_404(Service, pk=kwargs["pk"])
        require_manage_shop(request.user, service.shop_id)
        service.delete()
        return success_response(
            details="Service deleted successfully.",
            code="SERVICE_DELETED",
            data=None,
        )
