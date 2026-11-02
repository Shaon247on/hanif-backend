import sys

filepath = 'apps/user/serializers.py'
with open(filepath, 'r') as f:
    content = f.read()

old_block = """    role = (getattr(user, "role", "") or "").upper()
    is_admin = (
        role in (UserRole.ADMIN, UserRole.SUPER_ADMIN, "ADMIN", "SUPER_ADMIN")
        or getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
    )

    if is_admin:
        shops = Shop.objects.all().order_by("id")
    elif role in ("BARBER", "STAFF", "MANAGER") or hasattr(user, "barber_profile"):
        shop_ids = set()
        if hasattr(user, "barber_profile") and user.barber_profile and user.barber_profile.shop_id:
            shop_ids.add(user.barber_profile.shop_id)
        if hasattr(user, "shops") and user.shops.exists():
            shop_ids.update(user.shops.values_list("id", flat=True))
        if not shop_ids:
            return []
        shops = Shop.objects.filter(id__in=shop_ids).order_by("id")"""

new_block = """    role = (getattr(user, "role", "") or "").upper()

    if role == "SUPER_ADMIN" or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        shops = Shop.objects.all().order_by("id")
    elif role == "ADMIN":
        shops = Shop.objects.filter(owner=user).order_by("id")
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
        shops = Shop.objects.filter(id__in=shop_ids).order_by("id")"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Done")
else:
    print("Block not found!")
