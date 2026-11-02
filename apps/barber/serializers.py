from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from rest_framework import serializers

from apps.booking.models import ShopReview
from apps.common.enums import Status
from apps.core.serializers import ExtendedImageField
from apps.service.models import Service
from apps.user.enums import UserRole

from .models import Barber

User = get_user_model()


class BarberSerializer(serializers.ModelSerializer):
    name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True)
    image = ExtendedImageField(write_only=True, required=False, allow_null=True)
    services = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)

    user_details = serializers.SerializerMethodField(read_only=True)
    assigned_services = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Barber
        fields = [
            "id",
            "user",
            "shop",
            "specialty",
            "bio",
            "experience_years",
            "is_available",
            "commission_rate",
            "role",
            "calendar_access",
            "client_details_access",
            "name",
            "email",
            "phone",
            "image",
            "services",
            "user_details",
            "assigned_services",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "user", "created_at", "updated_at")

    def get_user_details(self, obj):
        user = obj.user
        request = self.context.get("request")
        image_url = None
        if user.image:
            image_url = user.image.url
            if request:
                image_url = request.build_absolute_uri(image_url)
        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "image": image_url,
        }

    def get_assigned_services(self, obj):
        services = Service.objects.filter(barbers=obj.user)
        return [
            {
                "id": s.id,
                "name": s.name,
                "price": s.price,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
        ]

    def create(self, validated_data):
        name = validated_data.pop("name")
        email = validated_data.pop("email")
        phone = validated_data.pop("phone", "")
        image = validated_data.pop("image", None)
        service_ids = validated_data.pop("services", [])

        user = User.objects.filter(email=email).first()
        if user and hasattr(user, "barber_profile"):
            raise serializers.ValidationError({"email": "A barber already exists with this email."})
        # This flow resets the password, so it must never take over a staff or admin account.
        if user and user.role != UserRole.USER:
            raise serializers.ValidationError({"email": "This email already belongs to a staff or admin account."})

        import secrets

        generated_password = secrets.token_urlsafe(12)
        if not user:
            user = User(email=email)
            user.set_unique_username()

        user.full_name = name
        user.phone = phone
        user.role = UserRole.BARBER
        user.is_active = True
        user.status = Status.ACTIVE
        user.set_password(generated_password)
        if image:
            user.image = image
        # In case an old user somehow lacks a username
        if not user.username:
            user.set_unique_username()
        user.save()

        barber = Barber.objects.create(user=user, **validated_data)

        if service_ids:
            services = Service.objects.filter(id__in=service_ids, shop=barber.shop)
            for service in services:
                service.barbers.add(user)

        barber.generated_password = generated_password
        return barber

    def update(self, instance, validated_data):
        name = validated_data.pop("name", None)
        email = validated_data.pop("email", None)
        phone = validated_data.pop("phone", None)
        image = validated_data.pop("image", None)
        service_ids = validated_data.pop("services", None)

        user = instance.user
        if name is not None:
            user.full_name = name
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if image is not None:
            user.image = image
        user.save()

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if service_ids is not None:
            old_services = Service.objects.filter(barbers=user)
            for service in old_services:
                service.barbers.remove(user)
            new_services = Service.objects.filter(id__in=service_ids, shop=instance.shop)
            for service in new_services:
                service.barbers.add(user)

        return instance


class BarberListSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.username", read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    review = serializers.SerializerMethodField()
    user_details = serializers.SerializerMethodField(read_only=True)
    assigned_services = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Barber
        fields = [
            "id",
            "user",
            "user_name",
            "shop",
            "shop_name",
            "specialty",
            "is_available",
            "experience_years",
            "role",
            "calendar_access",
            "client_details_access",
            "review",
            "user_details",
            "assigned_services",
        ]

    def get_review(self, obj):
        reviews = ShopReview.objects.filter(booking__appointments__barber=obj).aggregate(
            average_rating=Avg("rating"), count=Count("id", distinct=True)
        )
        return {"count": reviews["count"] or 0, "average_rating": round(reviews["average_rating"] or 0, 1)}

    def get_user_details(self, obj):
        user = obj.user
        request = self.context.get("request")
        image_url = None
        if user.image:
            image_url = user.image.url
            if request:
                image_url = request.build_absolute_uri(image_url)
        details = {
            "id": user.id,
            "name": user.full_name,
            "image": image_url,
        }
        if self.context.get("include_contact_details"):
            details["email"] = user.email
            details["phone"] = user.phone
        return details

    def get_assigned_services(self, obj):
        services = Service.objects.filter(barbers=obj.user)
        return [
            {
                "id": s.id,
                "name": s.name,
                "price": s.price,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
        ]



class BarberShopOptionSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Barber
        fields = ["id", "name"]
