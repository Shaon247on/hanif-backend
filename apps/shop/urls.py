from django.urls import path

from .views import (
    ShopDetailsUpdateDeleteAPIView,
    ShopGalleryDetailsUpdateDeleteAPIView,
    ShopGalleryListCreateAPIView,
    ShopGoogleReviewsAPIView,
    ShopListCreateAPIView,
    ShopPaymentSettingsAPIView,
    SelectActiveShopAPIView,
    ManagerListCreateAPIView,
    ManagerDetailUpdateDeleteAPIView,
)

urlpatterns = [
    path("shops/managers/", ManagerListCreateAPIView.as_view(), name="shop-manager-list-create"),
    path("shops/managers/<uuid:pk>/", ManagerDetailUpdateDeleteAPIView.as_view(), name="shop-manager-detail-update-delete"),
    path("shops/", ShopListCreateAPIView.as_view(), name="shop-list-create"),
    path("shops/select/", SelectActiveShopAPIView.as_view(), name="shop-select-active"),
    path("shops/<int:pk>/", ShopDetailsUpdateDeleteAPIView.as_view(), name="shop-detail-update-delete"),
    path("shops/<int:pk>/google-reviews/", ShopGoogleReviewsAPIView.as_view(), name="shop-google-reviews"),
    path("shops/<int:pk>/payment-settings/", ShopPaymentSettingsAPIView.as_view(), name="shop-payment-settings"),
    path("shops/gallery/", ShopGalleryListCreateAPIView.as_view(), name="shop-gallery-list-create"),
    path(
        "shops/gallery/<int:pk>/",
        ShopGalleryDetailsUpdateDeleteAPIView.as_view(),
        name="shop-gallery-detail-update-delete",
    ),
]
