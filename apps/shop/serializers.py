from django.db.models import Avg, Count
from rest_framework import serializers

from apps.core.serializers import ExtendedImageField

from .models import Shop, ShopGallery


class ShopBasicSerializer(serializers.ModelSerializer):
    logo = ExtendedImageField(required=False, allow_null=True)
    cover_image = ExtendedImageField(required=False, allow_null=True)

    class Meta:  # type: ignore[override]
        model = Shop
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "cover_image",
            "location",
            "phone",
            "email",
            "payment_gateway_enabled",
            "created_at",
        ]
        read_only_fields = (
            "created_at",
            "id",
        )


class ImageSerializer(serializers.ModelSerializer):
    image = ExtendedImageField(required=False)

    class Meta:  # type: ignore[override]
        model = ShopGallery
        fields = [
            "id",
            "shop",
            "image",
            "display_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "created_at",
            "updated_at",
            "id",
        )


class ShopSerializer(serializers.ModelSerializer):
    class Meta:  # type: ignore[override]
        model = Shop
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "cover_image",
            "location",
            "about_us",
            "phone",
            "email",
            "whatsapp",
            "facebook",
            "instagram",
            "tiktok",
            "twitter",
            "youtube",
            "google_review_link",
            "google_place_id",
            "payment_gateway_enabled",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "created_at",
            "updated_at",
            "id",
        )


class ShopListSerializer(serializers.ModelSerializer):
    review = serializers.SerializerMethodField()

    class Meta:  # type: ignore[override]
        model = Shop
        fields = [
            "id",
            "name",
            "logo",
            "cover_image",
            "location",
            "payment_gateway_enabled",
            "review",
        ]

    def get_review(self, obj):
        reviews = obj.reviews.aggregate(average_rating=Avg("rating"), count=Count("id"))
        return {"count": reviews["count"] or 0, "average_rating": round(reviews["average_rating"] or 0, 1)}


class ShopDetailsSerializer(serializers.ModelSerializer):
    images = ImageSerializer(many=True, read_only=True)

    class Meta:  # type: ignore[override]
        model = Shop
        fields = [
            "id",
            "name",
            "slug",
            "logo",
            "cover_image",
            "location",
            "about_us",
            "phone",
            "email",
            "whatsapp",
            "facebook",
            "instagram",
            "tiktok",
            "twitter",
            "youtube",
            "google_review_link",
            "google_place_id",
            "payment_gateway_enabled",
            "created_at",
            "updated_at",
            "images",
        ]
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )
