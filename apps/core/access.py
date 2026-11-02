"""
Shop-level access rules shared by every app.

Roles:
    - SUPER_ADMIN / ADMIN: every shop.
    - MANAGER: the single shop they are assigned to.
    - BARBER: read/operate within their own shop.
    - USER: only their own data (enforced by each view).

Usage:
    from apps.core.access import require_access_shop, require_manage_shop

    require_manage_shop(request.user, shop_id)
"""

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.exceptions import PermissionDenied

GLOBAL_ADMIN_ROLES = {"ADMIN", "SUPER_ADMIN"}
SHOP_STAFF_ROLES = GLOBAL_ADMIN_ROLES | {"MANAGER", "BARBER"}


def get_role(user) -> str:
    return str(getattr(user, "role", "") or "").upper()


def is_global_admin(user) -> bool:
    """Admins reach every shop. is_staff/is_superuser mirror get_user_shops()."""
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_superuser or user.is_staff or get_role(user) in GLOBAL_ADMIN_ROLES)


def is_shop_staff(user) -> bool:
    """True for anyone who works in a shop, whichever shop that is."""
    if not getattr(user, "is_authenticated", False):
        return False
    return is_global_admin(user) or get_role(user) in SHOP_STAFF_ROLES


def get_managed_shop_ids(user) -> set[int]:
    if get_role(user) != "MANAGER":
        return set()
    return set(user.managed_shops.values_list("id", flat=True))


def get_barber_shop_id(user):
    try:
        return user.barber_profile.shop_id
    except (AttributeError, ObjectDoesNotExist):
        return None


def get_accessible_shop_ids(user):
    """Return the shop IDs a user works in, or None when they reach every shop."""
    if is_global_admin(user):
        return None
    if not getattr(user, "is_authenticated", False):
        return set()
    shop_ids = get_managed_shop_ids(user)
    barber_shop_id = get_barber_shop_id(user)
    if barber_shop_id:
        shop_ids.add(barber_shop_id)
    return shop_ids


def _as_shop_id(shop_id):
    try:
        return int(shop_id)
    except (TypeError, ValueError):
        return None


def can_manage_shop(user, shop_id) -> bool:
    """Admins, and the manager assigned to this shop."""
    if is_global_admin(user):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    return _as_shop_id(shop_id) in get_managed_shop_ids(user)


def can_access_shop(user, shop_id) -> bool:
    """Anyone who can manage the shop, plus the barbers working in it."""
    accessible = get_accessible_shop_ids(user)
    return accessible is None or _as_shop_id(shop_id) in accessible


def require_manage_shop(user, shop_id) -> None:
    if not can_manage_shop(user, shop_id):
        raise PermissionDenied("You do not have permission to manage this shop.")


def require_access_shop(user, shop_id) -> None:
    if not can_access_shop(user, shop_id):
        raise PermissionDenied("You do not have access to this shop.")


def scope_to_user_shops(queryset, user, field: str = "shop_id"):
    """Limit a queryset to the shops the user works in."""
    accessible = get_accessible_shop_ids(user)
    if accessible is None:
        return queryset
    return queryset.filter(**{f"{field}__in": accessible})
