"""
Reusable DRF permission classes.

Usage:
    from apps.core.permissions import IsActiveUser, IsAdmin

    class MyView(APIView):
        permission_classes = [IsAdmin]
"""

from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request

from apps.core.access import is_global_admin, is_shop_staff


class IsActiveUser(IsAuthenticated):
    """Allow access only to authenticated users with status=ACTIVE."""

    def has_permission(self, request: Request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return getattr(request.user, "is_active", False) and getattr(request.user, "status", 0) == 1


class IsAdmin(IsActiveUser):
    """Allow access only to admin users and managers."""

    def has_permission(self, request: Request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return getattr(request.user, "role", "") in ("ADMIN", "SUPER_ADMIN", "MANAGER")


class IsGlobalAdmin(IsActiveUser):
    """Allow access only to admins, who reach every shop."""

    def has_permission(self, request: Request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return is_global_admin(request.user)


class IsShopStaff(IsActiveUser):
    """Allow access to anyone working in a shop (admin, manager, barber)."""

    def has_permission(self, request: Request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return is_shop_staff(request.user)


class IsSuperAdmin(IsActiveUser):
    """Allow access only to super admin users."""

    def has_permission(self, request: Request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        return getattr(request.user, "role", "") == "SUPER_ADMIN"


class IsAdminOrReadOnly(BasePermission):
    """
    Allow read access to anyone, write access only to admins.

    Safe methods: GET, HEAD, OPTIONS
    """

    def has_permission(self, request: Request, view) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "role", "") in ("ADMIN", "SUPER_ADMIN", "MANAGER")


class IsOwner(BasePermission):
    """
    Object-level permission: allow access only if the object's `user` field
    matches the requesting user.

    Requires the model to have a `user` field or override `get_owner()`.
    """

    def has_object_permission(self, request: Request, view, obj) -> bool:
        owner = getattr(obj, "user", None)
        if owner is None:
            return False
        return owner == request.user
