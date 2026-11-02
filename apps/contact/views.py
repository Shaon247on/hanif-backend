from django.db.models import Q
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.contact import services as contact_services
from apps.contact.models import FAQ, ContactMessage, Policy, Terms
from apps.contact.serializers import (
    ContactCreateSerializer,
    ContactMessageSerializer,
    ContactUserSerializer,
    FAQSerializer,
    PolicySerializer,
    TermsSerializer,
)
from apps.core.access import is_shop_staff
from apps.core.pagination import NoPagination
from apps.core.permissions import IsAdminOrReadOnly, IsShopStaff
from apps.core.responses import success_response
from apps.user.enums import UserRole
from apps.user.models import User
from apps.user.services import get_or_create_customer


# ---------------------------------------------------------------------------
# Terms & Policy (singleton-like: get_or_create pk=1)
# ---------------------------------------------------------------------------
class TermsAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update terms and conditions."""

    serializer_class = TermsSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = NoPagination
    http_method_names = ["get", "patch"]

    def get_object(self):
        obj, _ = Terms.objects.get_or_create(pk=1)
        return obj

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response("Terms retrieved.", data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Terms updated.", data=serializer.data)


class PolicyAPIView(generics.RetrieveUpdateAPIView):
    """Retrieve or update privacy policy."""

    serializer_class = PolicySerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = NoPagination
    http_method_names = ["get", "patch"]

    def get_object(self):
        obj, _ = Policy.objects.get_or_create(pk=1)
        return obj

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response("Policy retrieved.", data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Policy updated.", data=serializer.data)


# ---------------------------------------------------------------------------
# FAQ
# ---------------------------------------------------------------------------
class FAQListCreateAPIView(generics.ListCreateAPIView):
    """List all FAQs or create a new one."""

    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    permission_classes = [IsAdminOrReadOnly]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return success_response("FAQs retrieved.", data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(
            "FAQ created.",
            data=serializer.data,
            status_code=status.HTTP_201_CREATED,
        )


class FAQDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a FAQ."""

    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    permission_classes = [IsAdminOrReadOnly]
    http_method_names = ["get", "patch", "delete"]

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response("FAQ retrieved.", data=serializer.data)

    def partial_update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("FAQ updated.", data=serializer.data)

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return success_response("FAQ deleted.", status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Contact & Customer Management
# ---------------------------------------------------------------------------
def _get_contact_users_list_response(request):
    """Retrieve all users with role 'USER' / 'user'."""
    users = User.objects.filter(
        Q(role__iexact="user") | Q(role=UserRole.USER)
    ).order_by("-date_joined")

    search = request.query_params.get("search") or request.query_params.get("q")
    if search:
        search = search.strip()
        users = users.filter(
            Q(full_name__icontains=search)
            | Q(email__icontains=search)
            | Q(phone__icontains=search)
            | Q(username__icontains=search)
        )

    serializer = ContactUserSerializer(users, many=True, context={"request": request})
    return success_response("Contacts retrieved.", data=serializer.data, code="CONTACTS_RETRIEVED")


def _submit_contact_message(request, full_name, email, phone, message):
    """Public contact form: stores the message without touching any account."""
    if not message:
        return error_response(details="Message is required.", code="MESSAGE_REQUIRED")

    contact_msg = ContactMessage.objects.create(full_name=full_name or email, email=email, phone=phone, message=message)
    try:
        contact_services.notify_admin_of_contact(contact_msg)
    except Exception:
        pass

    return success_response(
        details="Message sent successfully.",
        code="CONTACT_MESSAGE_SENT",
        data={"full_name": contact_msg.full_name, "email": contact_msg.email},
        status_code=status.HTTP_201_CREATED,
    )


def _handle_contact_create_or_submit(request):
    """
    Shop staff: creates or updates a User with role='USER' (customer),
    and if message is present, creates ContactMessage and notifies admin.
    Everyone else: submits the contact form only.
    """
    email = (request.data.get("email") or "").strip()
    if not email:
        return success_response(
            details="Email is required.",
            code="EMAIL_REQUIRED",
            data={},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    full_name = (request.data.get("full_name") or request.data.get("name") or "").strip()
    phone = (request.data.get("phone") or "").strip()
    address = (request.data.get("address") or "").strip()
    message = (request.data.get("message") or "").strip()
    image = request.FILES.get("image")

    if not is_shop_staff(request.user):
        return _submit_contact_message(request, full_name, email, phone, message)

    user, is_new = get_or_create_customer(email, full_name, phone, address)
    if image and not user.image:
        user.image = image
        user.save(update_fields=["image"])

    # If message is provided, create ContactMessage and notify admin
    if message:
        contact_msg = ContactMessage.objects.create(
            full_name=full_name or user.full_name or email,
            email=email,
            phone=phone or user.phone or "",
            message=message,
        )
        try:
            contact_services.notify_admin_of_contact(contact_msg)
        except Exception:
            pass

    user_data = ContactUserSerializer(user, context={"request": request}).data
    return success_response(
        details="Contact created successfully." if is_new else "Contact saved successfully.",
        code="CONTACT_CREATED" if is_new else "CONTACT_SAVED",
        data=user_data,
        status_code=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK,
    )


class ContactCreateAPIView(APIView):
    """
    POST: Submit contact form or create customer/contact user (role='USER').
    GET: List all contacts / users with role 'USER' (admin only).
    """

    def get_permissions(self):
        if self.request.method == "GET":
            return [IsShopStaff()]
        return [AllowAny()]

    def get(self, request, *args, **kwargs):
        return _get_contact_users_list_response(request)

    def post(self, request, *args, **kwargs):
        return _handle_contact_create_or_submit(request)


class ContactListAPIView(APIView):
    """
    GET: List all contacts / users with role 'USER' (admin only).
    POST: Create a contact / customer user with role 'USER'.
    """

    permission_classes = [IsShopStaff]

    def get(self, request, *args, **kwargs):
        return _get_contact_users_list_response(request)

    def post(self, request, *args, **kwargs):
        return _handle_contact_create_or_submit(request)
