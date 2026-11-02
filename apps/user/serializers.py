"""User serializers — data validation only, no business logic."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.serializers import ContextMixin, ExtendedImageField
from apps.user.models import LocationService, User, Setting


def get_user_shops(user, context=None):
    """
    Returns assigned/accessible shops for the user:
    - If user is ADMIN or SUPER_ADMIN or superuser/staff: returns all shops.
    - If user is BARBER/STAFF/MANAGER or has a barber profile or owns shops: returns those shops.
    - If user is regular USER (customer): returns [].
    """
    if not user or not user.is_authenticated:
        return []

    from apps.shop.models import Shop
    from apps.shop.serializers import ShopBasicSerializer
    from apps.user.enums import UserRole

    role = (getattr(user, "role", "") or "").upper()

    if role in ("ADMIN", "SUPER_ADMIN") or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        shops = Shop.objects.all().order_by("id")
    elif role in ("BARBER", "STAFF", "MANAGER") or hasattr(user, "barber_profile"):
        shop_ids = set()
        if hasattr(user, "barber_profile") and user.barber_profile and user.barber_profile.shop_id:
            shop_ids.add(user.barber_profile.shop_id)
        if hasattr(user, "shops") and user.shops.exists():
            shop_ids.update(user.shops.values_list("id", flat=True))
        if hasattr(user, "managed_shops") and user.managed_shops.exists():
            shop_ids.update(user.managed_shops.values_list("id", flat=True))
            
        if not shop_ids:
            return []
        shops = Shop.objects.filter(id__in=shop_ids).order_by("id")
    elif hasattr(user, "shops") and user.shops.exists():
        shops = user.shops.all().order_by("id")
    else:
        return []

    return ShopBasicSerializer(shops, many=True, context=context or {}).data


def get_active_shop(user, context=None):
    """Return the user's persisted shop selection when it is still accessible."""
    if not user or not user.is_authenticated or not user.active_shop_id:
        return None
    accessible_shop_ids = {shop["id"] for shop in get_user_shops(user, context)}
    if user.active_shop_id not in accessible_shop_ids:
        return None
    from apps.shop.serializers import ShopBasicSerializer

    return ShopBasicSerializer(user.active_shop, context=context or {}).data


# ---------------------------------------------------------------------------
# Profile serializers
# ---------------------------------------------------------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    """Read-only user profile representation."""

    image = ExtendedImageField(required=False)
    shops = serializers.SerializerMethodField()
    active_shop = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "role",
            "full_name",
            "image",
            "phone",
            "address",
            "last_active_at",
            "date_joined",
            "shops",
            "active_shop",
        )
        read_only_fields = fields

    def get_shops(self, obj):
        return get_user_shops(obj, context=self.context)

    def get_active_shop(self, obj):
        return get_active_shop(obj, context=self.context)


class UserMiniProfile(serializers.ModelSerializer):
    image = ExtendedImageField(required=False)

    class Meta:
        model = User
        fields = ("id", "full_name", "image")
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Update user profile fields."""

    image = ExtendedImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            "full_name",
            "image",
            "phone",
            "address",
            "role"
        )


# ---------------------------------------------------------------------------
# Auth serializers
# ---------------------------------------------------------------------------
class RegisterSerializer(serializers.Serializer):
    """Validate registration input. User creation is in services.py."""

    full_name = serializers.CharField(required=False)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class EmailLoginSerializer(TokenObtainPairSerializer):
    """Login via email instead of username."""

    username_field = "email"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self.username_field] = serializers.EmailField()

    def validate(self, attrs):
        if "email" in attrs:
            attrs["email"] = attrs["email"].lower().strip()
        data = super().validate(attrs)
        
        # Auto-set active_shop if missing
        if not self.user.active_shop_id:
            accessible_shops = get_user_shops(self.user, context=self.context)
            if accessible_shops:
                self.user.active_shop_id = accessible_shops[0]["id"]
                self.user.save(update_fields=["active_shop_id"])
                
        user_data = UserProfileSerializer(self.user, context=self.context).data  # type: ignore
        data["user"] = user_data
        data["shops"] = user_data.get("shops", [])
        data["active_shop"] = user_data.get("active_shop")
        return data


class EmailVerificationSerializer(serializers.Serializer):
    """Validate email verification OTP."""

    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


class ResendOTPSerializer(serializers.Serializer):
    """Validate resend OTP request."""

    email = serializers.EmailField()
    type = serializers.ChoiceField(choices=["register", "password_reset"])

    def validate_email(self, value):
        return value.lower().strip()


# ---------------------------------------------------------------------------
# Password serializers
# ---------------------------------------------------------------------------
class PasswordChangeSerializer(serializers.Serializer, ContextMixin):
    """Validate old password change flow."""

    password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])
    confirm_password = serializers.CharField()

    def validate_password(self, value):
        user = self.get_context_user()
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Validate password reset request."""

    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class PasswordOTPVerifySerializer(serializers.Serializer):
    """Validate OTP verification."""

    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validate password reset with OTP."""

    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        value = value.strip()
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only digits.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        return attrs


# ---------------------------------------------------------------------------
# Location serializers
# ---------------------------------------------------------------------------
class LocationServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LocationService
        fields = ("id", "location_name", "location_link")
        read_only_fields = ("id",)


# ---------------------------------------------------------------------------
# Settings serializers
# ---------------------------------------------------------------------------
class SettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Setting
        fields = (
            "push_notifications_enabled",
            "email_notifications_enabled",
            "sms_notifications_enabled",
            "dark_mode_enabled",
        )
