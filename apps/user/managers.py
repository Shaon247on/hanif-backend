"""Custom user manager."""

from django.contrib.auth.models import UserManager as BaseUserManager

from apps.user.enums import UserRole


class UserManager(BaseUserManager):
    """Custom manager that handles role assignment during user creation."""

    def create_user(self, email, password=None, **extra_fields):  # type: ignore
        """Create a regular user."""
        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email)
        extra_fields.setdefault("role", UserRole.USER)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)

        # Generate username from email if not provided
        if "username" not in extra_fields or not extra_fields["username"]:
            extra_fields["username"] = email.split("@")[0]

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):  # type: ignore
        """Create a superuser."""
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        extra_fields["is_active"] = True
        extra_fields["role"] = UserRole.SUPER_ADMIN

        return self.create_user(email, password, **extra_fields)
