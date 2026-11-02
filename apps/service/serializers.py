from rest_framework import serializers

from apps.barber.models import Barber
from apps.service.models import Service
from apps.service.models import ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ["id", "shop", "name", "display_order", "is_active", "created_at", "updated_at"]
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        shop = attrs.get("shop") or getattr(self.instance, "shop", None)
        name = (attrs.get("name") or getattr(self.instance, "name", "")).strip()
        duplicates = ServiceCategory.objects.filter(shop=shop, name__iexact=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"name": "This category already exists."})
        attrs["name"] = name
        return attrs

class ServiceListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    barbers = serializers.SerializerMethodField()

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "price",
            "duration_minutes",
            "category",
            "barbers",
        ]
        read_only_fields = (
            "created_at",
            "updated_at",
            "id",
        )

    def get_category(self, obj):
        return {"id": obj.category_id, "name": obj.category.name}

    def get_barbers(self, obj):
        return list(Barber.objects.filter(user__in=obj.barbers.all()).values_list("id", flat=True))


class ServiceSerializer(serializers.ModelSerializer):
    barbers = serializers.PrimaryKeyRelatedField(
        queryset=Barber.objects.all(), many=True, required=False
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "category",
            "shop",
            "barbers",
            "name",
            "image",
            "description",
            "price",
            "duration_minutes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = (
            "created_at",
            "updated_at",
            "id",
        )

    def validate(self, attrs):
        shop = attrs.get("shop") or getattr(self.instance, "shop", None)
        if self.instance and "shop" in attrs and attrs["shop"].id != self.instance.shop_id:
            raise serializers.ValidationError({"shop": "A service cannot be moved to another shop."})
        category = attrs.get("category")
        if category and shop and category.shop_id != shop.id:
            raise serializers.ValidationError({"category": "This category belongs to another shop."})
        if shop and any(barber.shop_id != shop.id for barber in attrs.get("barbers", [])):
            raise serializers.ValidationError({"barbers": "All barbers must belong to this shop."})
        return attrs

    def create(self, validated_data):
        barbers = validated_data.pop("barbers", [])
        instance = super().create(validated_data)
        # Add the User objects related to the provided Barber instances
        if barbers:
            instance.barbers.set([b.user for b in barbers])
        return instance

    def update(self, instance, validated_data):
        barbers = validated_data.pop("barbers", None)
        instance = super().update(instance, validated_data)
        if barbers is not None:
            instance.barbers.set([b.user for b in barbers])
        return instance

    def to_representation(self, instance):
        # Convert User IDs back to Barber IDs for the response
        rep = super().to_representation(instance)
        # Find Barbers that match these Users
        barber_ids = Barber.objects.filter(user__in=instance.barbers.all()).values_list('id', flat=True)
        rep["barbers"] = list(barber_ids)
        return rep