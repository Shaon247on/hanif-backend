import os
import sys

filepath = 'apps/shop/views.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace ManagerListCreateAPIView definition up to the end
parts = content.split('class ManagerListCreateAPIView(APIView):')
if len(parts) < 2:
    print("Class not found")
    sys.exit(1)

new_code = """class ManagerListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
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
                managers = User.objects.filter(role="MANAGER", managed_shops__in=manager_shop_ids).distinct()

        data = []
        for m in managers:
            m_shops = m.managed_shops.all()
            # If admin, only show shops they own. If super admin or manager, show all.
            if request.user.role == "ADMIN":
                m_shops = [s for s in m_shops if s.owner == request.user]
            
            data.append({
                "id": m.id,
                "email": m.email,
                "full_name": m.full_name,
                "phone": m.phone,
                "is_active": m.is_active,
                "role": m.role,
                "shops": [{"id": s.id, "name": s.name} for s in m_shops]
            })
            
        return success_response(details="Managers retrieved.", code="MANAGERS_RETRIEVED", data=data)

    def post(self, request, *args, **kwargs):
        from apps.user.models import User
        from django.contrib.auth.hashers import make_password
        from apps.notification.utils import send_push_and_email
        
        shop_ids = request.data.get("shop_ids", [])
        email = request.data.get("email")
        password = request.data.get("password")
        full_name = request.data.get("full_name", "")
        phone = request.data.get("phone", "")

        if not shop_ids or not isinstance(shop_ids, list) or not email or not password:
            return success_response(details="shop_ids (list), email, and password are required.", code="MISSING_PARAMS", data={}, status_code=400)
        
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can create managers.", code="PERMISSION_DENIED", data={}, status_code=403)

        shops = Shop.objects.filter(id__in=shop_ids)
        if len(shops) != len(shop_ids):
            return success_response(details="One or more invalid shop IDs.", code="INVALID_SHOPS", data={}, status_code=400)

        # Ensure the admin owns all these shops (unless super admin)
        if request.user.role == "ADMIN":
            for shop in shops:
                if shop.owner != request.user:
                    return success_response(details=f"You do not own shop ID {shop.id}.", code="PERMISSION_DENIED", data={}, status_code=403)

        user = User.objects.filter(email=email).first()
        is_new = False
        if not user:
            user = User(email=email, full_name=full_name, phone=phone, role="MANAGER")
            user.set_unique_username()
            user.password = make_password(password)
            user.save()
            is_new = True
        else:
            if user.role not in ["MANAGER", "ADMIN", "SUPER_ADMIN"]:
                user.role = "MANAGER"
                user.save(update_fields=["role"])

        for shop in shops:
            shop.managers.add(user)
        
        if is_new:
            send_push_and_email(
                user=user,
                title="Welcome as a Manager!",
                message=f"You have been added as a manager. Your login email is {email} and your password is: {password}",
                notif_type="system",
                send_email=True
            )

        return success_response(
            details="Manager created and assigned successfully.",
            code="MANAGER_CREATED",
            data={
                "manager_id": user.id, 
                "email": user.email, 
                "full_name": user.full_name, 
                "assigned_shops": [{"id": s.id, "name": s.name} for s in shops]
            }
        )

class ManagerDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk, *args, **kwargs):
        from apps.user.models import User
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Permission denied.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        manager = get_object_or_404(User, pk=pk, role="MANAGER")
        
        m_shops = manager.managed_shops.all()
        if request.user.role == "ADMIN":
            m_shops = [s for s in m_shops if s.owner == request.user]
            if not m_shops:
                return success_response(details="You do not have access to this manager.", code="PERMISSION_DENIED", data={}, status_code=403)
        
        data = {
            "id": manager.id,
            "email": manager.email,
            "full_name": manager.full_name,
            "phone": manager.phone,
            "is_active": manager.is_active,
            "role": manager.role,
            "shops": [{"id": s.id, "name": s.name} for s in m_shops]
        }
        return success_response(details="Manager retrieved.", code="MANAGER_RETRIEVED", data=data)

    def patch(self, request, pk, *args, **kwargs):
        from apps.user.models import User
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can update managers.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        manager = get_object_or_404(User, pk=pk, role="MANAGER")
        
        # Verify access
        if request.user.role == "ADMIN":
            if not manager.managed_shops.filter(owner=request.user).exists():
                return success_response(details="You do not have access to this manager.", code="PERMISSION_DENIED", data={}, status_code=403)
        
        if "full_name" in request.data:
            manager.full_name = request.data["full_name"]
        if "phone" in request.data:
            manager.phone = request.data["phone"]
        if "is_active" in request.data:
            manager.is_active = request.data["is_active"]
            manager.status = 1 if manager.is_active else 0
            
        if "password" in request.data and request.data["password"]:
            from django.contrib.auth.hashers import make_password
            manager.password = make_password(request.data["password"])
            
        manager.save()
        
        if "shop_ids" in request.data and isinstance(request.data["shop_ids"], list):
            shop_ids = request.data["shop_ids"]
            shops = Shop.objects.filter(id__in=shop_ids)
            if len(shops) != len(shop_ids):
                return success_response(details="One or more invalid shop IDs.", code="INVALID_SHOPS", data={}, status_code=400)
                
            if request.user.role == "ADMIN":
                for shop in shops:
                    if shop.owner != request.user:
                        return success_response(details=f"You do not own shop ID {shop.id}.", code="PERMISSION_DENIED", data={}, status_code=403)
                
                # Replace ONLY the shops owned by this admin
                other_admin_shops = manager.managed_shops.exclude(owner=request.user)
                manager.managed_shops.set(list(other_admin_shops) + list(shops))
            else:
                manager.managed_shops.set(shops)
        
        m_shops = manager.managed_shops.all()
        if request.user.role == "ADMIN":
            m_shops = [s for s in m_shops if s.owner == request.user]
            
        data = {
            "id": manager.id,
            "email": manager.email,
            "full_name": manager.full_name,
            "phone": manager.phone,
            "is_active": manager.is_active,
            "role": manager.role,
            "shops": [{"id": s.id, "name": s.name} for s in m_shops]
        }
        return success_response(details="Manager updated.", code="MANAGER_UPDATED", data=data)
        
    def put(self, request, pk, *args, **kwargs):
        return self.patch(request, pk, *args, **kwargs)
        
    def delete(self, request, pk, *args, **kwargs):
        from apps.user.models import User
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can delete managers.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        manager = get_object_or_404(User, pk=pk, role="MANAGER")
        
        if request.user.role == "ADMIN":
            admin_shops = manager.managed_shops.filter(owner=request.user)
            if not admin_shops.exists():
                return success_response(details="You do not have access to this manager.", code="PERMISSION_DENIED", data={}, status_code=403)
            
            # Remove manager from this admin's shops
            for shop in admin_shops:
                shop.managers.remove(manager)
            
            # If manager has no other shops, we could delete the user or leave them
            if not manager.managed_shops.exists():
                manager.delete()
        else:
            manager.delete()
        
        return success_response(details="Manager deleted/removed successfully.", code="MANAGER_DELETED", data={})
"""

# Replace everything after class ManagerListCreateAPIView(APIView):
final_content = parts[0] + new_code

with open(filepath, 'w') as f:
    f.write(final_content)

print("Done")
