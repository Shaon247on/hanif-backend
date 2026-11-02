import sys

filepath = 'apps/shop/views.py'
with open(filepath, 'r') as f:
    content = f.read()

old_block = """    def get(self, request, *args, **kwargs):
        from apps.user.models import User
        shop_id = request.query_params.get("shop_id")
        
        if request.user.role not in ["ADMIN", "SUPER_ADMIN", "MANAGER"]:
            return success_response(details="Permission denied.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        if shop_id:
            shop = get_object_or_404(Shop, pk=shop_id)
            if request.user.role in ["ADMIN", "MANAGER"] and shop.owner != request.user and not shop.managers.filter(id=request.user.id).exists():
                return success_response(details="You do not have access to this shop.", code="PERMISSION_DENIED", data={}, status_code=403)
            managers = shop.managers.all()
        else:
            # If no shop_id, list managers for all shops owned by the admin
            if request.user.role == "SUPER_ADMIN":
                managers = User.objects.filter(role="MANAGER")
            elif request.user.role == "ADMIN":
                managers = User.objects.filter(role="MANAGER", managed_shops__owner=request.user).distinct()
            else: # MANAGER can only see themselves or their colleagues? Let's say they can only see managers of their shops
                manager_shop_ids = request.user.managed_shops.values_list('id', flat=True)
                managers = User.objects.filter(role="MANAGER", managed_shops__in=manager_shop_ids).distinct()"""

new_block = """    def get(self, request, *args, **kwargs):
        from apps.user.models import User
        shop_id = request.query_params.get("shop_id")
        
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Permission denied.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        if shop_id:
            shop = get_object_or_404(Shop, pk=shop_id)
            if request.user.role == "ADMIN" and shop.owner != request.user:
                return success_response(details="You do not have access to this shop.", code="PERMISSION_DENIED", data={}, status_code=403)
            managers = shop.managers.all()
        else:
            # If no shop_id, list managers for all shops owned by the admin
            if request.user.role == "SUPER_ADMIN":
                managers = User.objects.filter(role="MANAGER")
            elif request.user.role == "ADMIN":
                managers = User.objects.filter(role="MANAGER", managed_shops__owner=request.user).distinct()
            else:
                managers = User.objects.none()"""

if old_block in content:
    content = content.replace(old_block, new_block)
    with open(filepath, 'w') as f:
        f.write(content)
    print("Done")
else:
    print("Block not found!")
