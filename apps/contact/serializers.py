"""Contact serializers."""

from rest_framework import serializers

from apps.contact.models import FAQ, ContactMessage, Policy, Terms


class TermsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Terms
        fields = ("id", "title", "content", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class PolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = Policy
        fields = ("id", "title", "content", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ("id", "question", "answer", "order", "status", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class ContactMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactMessage
        fields = ("id", "full_name", "email", "phone", "message", "is_replied", "created_at")
        read_only_fields = ("id", "is_replied", "created_at")
        extra_kwargs = {
            "phone": {"required": False},
        }


from apps.core.serializers import ExtendedImageField
from apps.user.models import User


class ContactUserSerializer(serializers.ModelSerializer):
    """Serializer for contacts / customer users (role='USER')."""

    image = ExtendedImageField(required=False, allow_null=True)
    is_new_client = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "full_name",
            "email",
            "phone",
            "image",
            "address",
            "role",
            "status",
            "last_active_at",
            "date_joined",
            "is_new_client",
        )
        read_only_fields = ("id", "role", "status", "last_active_at", "date_joined", "is_new_client")

    def get_is_new_client(self, obj):
        # A new client is someone who hasn't completed any bookings yet
        # If you prefer to check if they have NO bookings at all:
        return not obj.bookings.exists()


class ContactCreateSerializer(serializers.Serializer):
    """Serializer for creating a contact / customer or submitting contact form."""

    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    image = ExtendedImageField(required=False, allow_null=True)
    address = serializers.CharField(max_length=500, required=False, allow_blank=True)
