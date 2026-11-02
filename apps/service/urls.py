"""Service URL configuration."""

from django.urls import path

from apps.service.views import (
    ServiceCategoryCreateListAPIView,
    ServiceCategoryDeleteAPIView,
    ServiceCreateListAPIView,
    ServiceUpdateDeleteAPIView,
)

urlpatterns = [
    path("categories/", ServiceCategoryCreateListAPIView.as_view(), name="service-category-list-create"),
    path("categories/<str:pk>/", ServiceCategoryDeleteAPIView.as_view(), name="service-category-delete"),
    path("services/", ServiceCreateListAPIView.as_view(), name="service-list-create"),
    path("services/<str:pk>/", ServiceUpdateDeleteAPIView.as_view(), name="service-detail-update-delete"),
]
