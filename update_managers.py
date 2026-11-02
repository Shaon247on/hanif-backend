import os
import sys

filepath = 'apps/shop/views.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace ManagerCreateAPIView definition up to the end
parts = content.split('class ManagerCreateAPIView(APIView):')
if len(parts) < 2:
    print("Class not found")
    sys.exit(1)

new_code = """class ManagerListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return success_response(details="shop_id is required.", code="MISSING_PARAMS", data={}, status_code=400)
            
        shop = get_object_or_404(Shop, pk=shop_id)
        if request.user.role not in ["ADMIN", "SUPER_ADMIN", "MANAGER"]:
            return success_response(details="Permission denied.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        if request.user.role in ["ADMIN", "MANAGER"] and shop.owner != request.user and not shop.managers.filter(id=request.user.id).exists():
            return success_response(details="You do not have access to this shop.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        managers = shop.managers.all()
        data = [
            {
                "id": m.id,
                "email": m.email,
                "full_name": m.full_name,
                "phone": m.phone,
                "is_active": m.is_active,
                "role": m.role
            } for m in managers
        ]
        return success_response(details="Managers retrieved.", code="MANAGERS_RETRIEVED", data=data)

    def post(self, request, *args, **kwargs):
        from apps.user.models import User
        from django.contrib.auth.hashers import make_password
        from apps.notification.utils import send_push_and_email
        
        shop_id = request.data.get("shop_id")
        email = request.data.get("email")
        password = request.data.get("password")
        full_name = request.data.get("full_name", "")
        phone = request.data.get("phone", "")

        if not shop_id or not email or not password:
            return success_response(details="shop_id, email, and password are required.", code="MISSING_PARAMS", data={}, status_code=400)

        shop = get_object_or_404(Shop, pk=shop_id)
        
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can create managers.", code="PERMISSION_DENIED", data={}, status_code=403)

        if request.user.role == "ADMIN" and shop.owner != request.user:
            return success_response(details="You do not own this shop.", code="PERMISSION_DENIED", data={}, status_code=403)

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

        shop.managers.add(user)
        
        if is_new:
            send_push_and_email(
                user=user,
                title="Welcome as a Manager!",
                message=f"You have been added as a manager for {shop.name}. Your login email is {email} and your password is: {password}",
                notif_type="system",
                send_email=True
            )

        return success_response(
            details="Manager created and assigned successfully.",
            code="MANAGER_CREATED",
            data={"manager_id": user.id, "email": user.email, "full_name": user.full_name, "shop_id": shop.id}
        )

class ManagerDetailUpdateDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk, *args, **kwargs):
        from apps.user.models import User
        shop_id = request.query_params.get("shop_id")
        if not shop_id:
            return success_response(details="shop_id is required.", code="MISSING_PARAMS", data={}, status_code=400)
            
        shop = get_object_or_404(Shop, pk=shop_id)
        manager = get_object_or_404(shop.managers.all(), pk=pk)
        
        data = {
            "id": manager.id,
            "email": manager.email,
            "full_name": manager.full_name,
            "phone": manager.phone,
            "is_active": manager.is_active,
            "role": manager.role
        }
        return success_response(details="Manager retrieved.", code="MANAGER_RETRIEVED", data=data)

    def patch(self, request, pk, *args, **kwargs):
        shop_id = request.data.get("shop_id") or request.query_params.get("shop_id")
        if not shop_id:
            return success_response(details="shop_id is required.", code="MISSING_PARAMS", data={}, status_code=400)
            
        shop = get_object_or_404(Shop, pk=shop_id)
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can update managers.", code="PERMISSION_DENIED", data={}, status_code=403)
        if request.user.role == "ADMIN" and shop.owner != request.user:
            return success_response(details="You do not own this shop.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        manager = get_object_or_404(shop.managers.all(), pk=pk)
        
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
        
        data = {
            "id": manager.id,
            "email": manager.email,
            "full_name": manager.full_name,
            "phone": manager.phone,
            "is_active": manager.is_active,
            "role": manager.role
        }
        return success_response(details="Manager updated.", code="MANAGER_UPDATED", data=data)
        
    def put(self, request, pk, *args, **kwargs):
        return self.patch(request, pk, *args, **kwargs)
        
    def delete(self, request, pk, *args, **kwargs):
        shop_id = request.data.get("shop_id") or request.query_params.get("shop_id")
        if not shop_id:
            return success_response(details="shop_id is required.", code="MISSING_PARAMS", data={}, status_code=400)
            
        shop = get_object_or_404(Shop, pk=shop_id)
        if request.user.role not in ["ADMIN", "SUPER_ADMIN"]:
            return success_response(details="Only admins can remove managers.", code="PERMISSION_DENIED", data={}, status_code=403)
        if request.user.role == "ADMIN" and shop.owner != request.user:
            return success_response(details="You do not own this shop.", code="PERMISSION_DENIED", data={}, status_code=403)
            
        manager = get_object_or_404(shop.managers.all(), pk=pk)
        shop.managers.remove(manager)
        
        return success_response(details="Manager removed from shop.", code="MANAGER_REMOVED", data={})
"""

# Replace everything after class ManagerCreateAPIView(APIView):
final_content = parts[0] + new_code

with open(filepath, 'w') as f:
    f.write(final_content)

print("Done")
