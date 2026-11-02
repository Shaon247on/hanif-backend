"""
User service layer — all business logic lives here.

Views call these functions; serializers only validate data.
This keeps views thin and business logic testable in isolation.
"""

import logging
import random
import secrets

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.user.enums import UserRole
from apps.user.models import OTP, LocationService, User

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def register_user(validated_data: dict, request=None) -> User:
    """
    Create a new user and trigger verification email.

    Args:
        validated_data: Validated data from RegisterSerializer
        request: The HTTP request (for building absolute URLs)

    Returns:
        The created User instance

    Raises:
        ValidationError: If username generation fails after retries
    """
    email = validated_data["email"]
    password = validated_data["password"]
    full_name = validated_data.get("full_name", "")
    phone = validated_data.get("phone", "")

    with transaction.atomic():
        user = User(email=email, is_active=False, is_staff=False, full_name=full_name, phone=phone)
        user.set_unique_username()
        user.set_password(password)

        for attempt in range(5):
            try:
                user.save()
                break
            except IntegrityError as exc:
                if "username" not in str(exc).lower() or attempt == 4:
                    raise ValidationError("Unable to create account. Please try again.") from exc
                user.set_unique_username()

    # Generate and save registration OTP
    otp = str(random.randint(100000, 999999))
    OTP.objects.create(user=user, otp=otp, type=OTP.OTPType.REGISTER)

    # Send verification email synchronously (without Celery)
    from apps.user.tasks import _send_verification_email

    try:
        _send_verification_email(str(user.pk), otp)
    except Exception:
        logger.exception("Failed to send verification email for user %s", user.pk)

    return user


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------
def verify_email(email: str, otp: str) -> dict:
    """
    Verify a user's email and activate their account using 6-digit OTP.

    Returns:
        Dict with access/refresh tokens and user data
    """
    try:
        user = User.objects.get(email=email)
    except ObjectDoesNotExist as exc:
        raise ValidationError("User not found.") from exc

    if user.is_active:
        raise ValidationError("Account is already verified. Please log in.")

    otp_obj = OTP.objects.filter(user=user, otp=otp, type=OTP.OTPType.REGISTER, is_used=False).order_by("-created_at").first()

    if not otp_obj:
        raise ValidationError("Invalid OTP.")

    if otp_obj.is_expired():
        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])
        raise ValidationError("OTP has expired. Please register again or request a new one.")

    otp_obj.is_used = True
    otp_obj.save(update_fields=["is_used"])

    user.is_active = True
    user.save(update_fields=["is_active"])

    # Send welcome email asynchronously
    try:
        from apps.user.tasks import send_welcome_email_task

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            send_welcome_email_task.apply(args=(str(user.pk),))
        else:
            send_welcome_email_task.delay(str(user.pk))
    except Exception:
        logger.warning("Could not queue welcome email for user %s", user.pk)

    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "role": user.role,
    }


def resend_otp(email: str, otp_type: str) -> None:
    """Generate and send a new OTP of specified type (register or password_reset) to the user."""
    try:
        user = User.objects.get(email=email)
    except ObjectDoesNotExist as exc:
        raise ValidationError("User not found.") from exc

    if otp_type == OTP.OTPType.REGISTER:
        if user.is_active:
            raise ValidationError("Account is already verified. Please log in.")
        # Mark existing active registration OTPs as used
        OTP.objects.filter(user=user, type=OTP.OTPType.REGISTER, is_used=False).update(is_used=True)
        # Generate new OTP
        otp = str(random.randint(100000, 999999))
        OTP.objects.create(user=user, otp=otp, type=OTP.OTPType.REGISTER)
        # Send email verification OTP synchronously
        from apps.user.tasks import _send_verification_email
        try:
            _send_verification_email(str(user.pk), otp)
        except Exception as exc:
            logger.exception("Failed to send verification email for user %s", user.pk)

    elif otp_type == OTP.OTPType.PASSWORD_RESET:
        # Mark existing active password reset OTPs as used
        OTP.objects.filter(user=user, type=OTP.OTPType.PASSWORD_RESET, is_used=False).update(is_used=True)
        # Generate new OTP
        otp = str(random.randint(100000, 999999))
        OTP.objects.create(user=user, otp=otp, type=OTP.OTPType.PASSWORD_RESET)
        # Send password reset OTP email
        try:
            from apps.user.tasks import send_password_reset_otp_task
            if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
                send_password_reset_otp_task.apply(args=(str(user.pk), otp))
            else:
                send_password_reset_otp_task.delay(str(user.pk), otp)
        except Exception:
            logger.warning("Celery unavailable, sending OTP email synchronously.")
            from apps.user.tasks import _send_password_reset_otp
            _send_password_reset_otp(str(user.pk), otp)
    else:
        raise ValidationError("Invalid OTP type.")


# ---------------------------------------------------------------------------
# Password management
# ---------------------------------------------------------------------------
def change_password(user: User, new_password: str) -> None:
    """Change a user's password."""
    user.set_password(new_password)
    user.save(update_fields=["password"])


def request_password_reset(email: str) -> None:
    """
    Generate OTP and send password reset email.

    Silently succeeds even if email doesn't exist (security best practice).
    """
    try:
        user = User.objects.get(email=email)
    except ObjectDoesNotExist:
        return  # Don't reveal whether email exists

    # Invalidate previous OTPs
    OTP.objects.filter(user=user, type=OTP.OTPType.PASSWORD_RESET, is_used=False).update(is_used=True)

    otp = str(random.randint(100000, 999999))
    OTP.objects.create(user=user, otp=otp, type=OTP.OTPType.PASSWORD_RESET)

    # Send OTP email asynchronously
    try:
        from apps.user.tasks import send_password_reset_otp_task

        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            send_password_reset_otp_task.apply(args=(str(user.pk), otp))
        else:
            send_password_reset_otp_task.delay(str(user.pk), otp)
    except Exception:
        logger.warning("Celery unavailable, sending OTP email synchronously.")
        from apps.user.tasks import _send_password_reset_otp

        _send_password_reset_otp(str(user.pk), otp)


def verify_otp(email: str, otp: str) -> bool:
    """Verify that an OTP is valid."""
    user = _get_user_by_email(email)

    otp_obj = OTP.objects.filter(user=user, otp=otp, type=OTP.OTPType.PASSWORD_RESET, is_used=False).order_by("-created_at").first()

    if not otp_obj:
        raise ValidationError("Invalid OTP.")

    if otp_obj.is_expired():
        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])
        raise ValidationError("OTP has expired.")

    return True


def reset_password(email: str, otp: str, new_password: str) -> User:
    """Reset password using OTP."""
    user = _get_user_by_email(email)

    otp_obj = OTP.objects.filter(user=user, otp=otp, type=OTP.OTPType.PASSWORD_RESET, is_used=False).order_by("-created_at").first()

    if not otp_obj:
        raise ValidationError("Invalid or already used OTP.")

    if otp_obj.is_expired():
        otp_obj.is_used = True
        otp_obj.save(update_fields=["is_used"])
        raise ValidationError("OTP has expired. Please request a new one.")

    user.set_password(new_password)
    user.save(update_fields=["password"])
    otp_obj.is_used = True
    otp_obj.save(update_fields=["is_used"])

    return user


def _get_user_by_email(email: str) -> User:
    """Get user by email or raise NotFound."""
    try:
        return User.objects.get(email=email)
    except ObjectDoesNotExist as exc:
        raise NotFound("User not found.") from exc


def get_location_service(user: User) -> LocationService | None:
    """Retrieve the location service for a user, or None if not set."""
    try:
        return LocationService.objects.get(user=user)
    except ObjectDoesNotExist:
        return None


def create_or_update_location_service(user: User, data: dict) -> LocationService:
    """Create or update the user's location service."""
    location_service, _ = LocationService.objects.update_or_create(
        user=user,
        defaults={
            "location_name": data.get("location_name"),
            "location_link": data.get("location_link"),
        },
    )
    return location_service

def get_or_create_customer(email: str, full_name: str = "", phone: str = "", address: str = "") -> tuple[User, bool]:
    """
    Find a customer by email or create one, so the same person is never registered twice.
    Details already on file are kept; only empty fields are filled in.
    """
    user = User.objects.filter(email__iexact=email).first()
    if user and user.role != UserRole.USER:
        raise ValidationError({"email": "This email already belongs to a staff or admin account."})

    if user:
        updates = {"full_name": full_name, "phone": phone, "address": address}
        changed = [field for field, value in updates.items() if value and not getattr(user, field)]
        for field in changed:
            setattr(user, field, updates[field])
        if changed:
            user.save(update_fields=changed)
        return user, False

    user = User.objects.create_user(
        username=secrets.token_urlsafe(12),
        email=email,
        password=secrets.token_urlsafe(12),
        full_name=full_name,
        phone=phone,
        address=address,
        role=UserRole.USER,
    )
    user.set_unique_username()
    user.save(update_fields=["username"])
    return user, True
