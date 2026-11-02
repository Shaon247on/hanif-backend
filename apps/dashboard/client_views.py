import os

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView

from apps.booking.models import Appointment, Booking
from apps.core.access import require_access_shop, require_manage_shop
from apps.core.permissions import IsAdmin, IsShopStaff
from apps.core.responses import error_response, success_response
from apps.shop.models import ClientGroup, Shop
from apps.user.enums import UserRole
from apps.user.models import User
from apps.user.serializers import UserProfileSerializer

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    TwilioClient = None


class ClientListCreateAPIView(APIView):
    """
    GET: List all clients for a shop.
    POST: Admin creates a new client.
    """

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id=None, *args, **kwargs):
        if not shop_id:
            shop_id = request.query_params.get("shop_id") or request.query_params.get("shop")
        if shop_id:
            require_access_shop(request.user, get_object_or_404(Shop, pk=shop_id).id)

        # Every customer account is a client of the business, whether or not they have booked.
        clients = User.objects.filter(role=UserRole.USER).order_by("-date_joined")

        search = (request.query_params.get("search") or "").strip()
        if search:
            clients = clients.filter(
                Q(full_name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search)
            )

        import datetime

        thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
        new_clients = clients.filter(date_joined__gte=thirty_days_ago)

        data = {
            "new_clients": UserProfileSerializer(new_clients, many=True, context={"request": request}).data,
            "all_clients": UserProfileSerializer(clients, many=True, context={"request": request}).data
        }
        
        return success_response(details="Clients retrieved", code="CLIENTS_RETRIEVED", data=data)

    def post(self, request, shop_id=None, *args, **kwargs):
        email = request.data.get("email")
        phone = request.data.get("phone", "")
        name = request.data.get("name", "")
        image = request.FILES.get("image")

        if not email:
            return success_response(details="Email is required.", code="EMAIL_REQUIRED", data={})

        if User.objects.filter(email=email).exists():
            return success_response(details="User with this email already exists.", code="USER_EXISTS", data={})

        import secrets

        user = User.objects.create_user(
            username=secrets.token_urlsafe(12),
            email=email,
            password=secrets.token_urlsafe(12),
            full_name=name,
            phone=phone,
            role=UserRole.USER,
        )
        if image:
            user.image = image
            
        user.set_unique_username()
        user.save()

        return success_response(
            details="Client created successfully", code="CLIENT_CREATED", data=UserProfileSerializer(user, context={"request": request}).data
        )


class ClientDetailAPIView(APIView):
    """GET: Client details and booking metrics for a specific shop."""

    permission_classes = [IsShopStaff]

    def get(self, request, shop_id, pk, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_access_shop(request.user, shop.id)
        client = get_object_or_404(User, pk=pk, role=UserRole.USER)

        bookings = Booking.objects.filter(shop=shop, customer=client)

        total_appointments = Appointment.objects.filter(booking__in=bookings).exclude(status="cancelled").count()
        cancellations = Appointment.objects.filter(booking__in=bookings, status="cancelled").count()

        last_visit_appt = (
            Appointment.objects.filter(booking__in=bookings, status__in=["completed", "in_progress"])
            .order_by("-appointment_date", "-start_time")
            .first()
        )

        total_revenue = (
            bookings.filter(status__in=["completed", "paid"]).aggregate(total=Sum("total_amount"))["total"] or 0.0
        )

        today = timezone.localdate()
        upcoming_bookings = bookings.filter(
            status__in=["pending", "confirmed"], appointments__appointment_date__gte=today
        ).distinct()

        past_bookings = bookings.filter(
            Q(status__in=["completed", "cancelled", "refunded"])
            | Q(appointments__appointment_date__lt=today)
        ).distinct()

        from apps.booking.serializers import BookingSerializer

        data = {
            "client": UserProfileSerializer(client, context={"request": request}).data,
            "metrics": {
                "total_appointments": total_appointments,
                "cancellations": cancellations,
                "last_visit": last_visit_appt.appointment_date if last_visit_appt else None,
                "total_revenue": float(total_revenue),
            },
            "upcoming_bookings": BookingSerializer(upcoming_bookings, many=True).data,
            "past_bookings": BookingSerializer(past_bookings, many=True).data,
        }

        return success_response(details="Client details retrieved", code="CLIENT_DETAILS", data=data)


class ClientMessageAPIView(APIView):
    """POST: Send Email/SMS to a list of clients."""

    permission_classes = [IsAdmin]

    def post(self, request, shop_id, *args, **kwargs):
        shop = get_object_or_404(Shop, pk=shop_id)
        require_manage_shop(request.user, shop.id)

        client_ids = request.data.get("client_ids", [])
        group_id = request.data.get("group_id")
        email_title = request.data.get("email_title", "")
        email_content = request.data.get("email_content", "")
        sms_content = request.data.get("sms_content", "")

        users = User.objects.none()
        if group_id:
            group = get_object_or_404(ClientGroup, pk=group_id, shop=shop)
            users = group.clients.all()
        elif client_ids:
            users = User.objects.filter(id__in=client_ids, role=UserRole.USER)

        if not users.exists():
            return success_response(details="No clients selected.", code="NO_CLIENTS", data={})

        emails = [u.email for u in users if u.email]
        phones = [u.phone for u in users if u.phone]

        results = {"emails_sent": 0, "sms_sent": 0}

        # Send Emails
        if email_title and email_content and emails:
            try:
                sent = send_mail(
                    subject=email_title,
                    message=email_content,
                    from_email=settings.DEFAULT_FROM_EMAIL
                    if hasattr(settings, "DEFAULT_FROM_EMAIL")
                    else "noreply@example.com",
                    recipient_list=emails,
                    fail_silently=True,
                )
                results["emails_sent"] = sent
            except Exception:
                pass

        # Send SMS via Twilio
        if sms_content and phones:
            if not TwilioClient:
                return success_response(details="Twilio package not installed.", code="TWILIO_MISSING", data=results)

            account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", os.environ.get("TWILIO_ACCOUNT_SID"))
            auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", os.environ.get("TWILIO_AUTH_TOKEN"))
            twilio_number = getattr(settings, "TWILIO_PHONE_NUMBER", os.environ.get("TWILIO_PHONE_NUMBER"))

            if account_sid and auth_token and twilio_number:
                client = TwilioClient(account_sid, auth_token)
                sms_sent = 0
                for phone in phones:
                    try:
                        client.messages.create(body=sms_content, from_=twilio_number, to=phone)
                        sms_sent += 1
                    except Exception as e:
                        print(f"Twilio error for {phone}: {e}")
                results["sms_sent"] = sms_sent
            else:
                return success_response(
                    details="Twilio credentials missing.", code="TWILIO_CREDS_MISSING", data=results
                )

        return success_response(details="Messages dispatched.", code="MESSAGES_SENT", data=results)


import csv
import io

from django.http import HttpResponse


class ClientImportAPIView(APIView):
    """
    GET: Download a sample CSV template for importing clients.
    POST: Upload a CSV file to bulk import clients.
    """

    permission_classes = [IsAdmin]

    def get(self, request, shop_id, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="client_import_template.csv"'

        writer = csv.writer(response)
        writer.writerow(["name", "email", "phone"])
        writer.writerow(["John Doe", "john@example.com", "+1234567890"])
        writer.writerow(["Jane Smith", "jane@example.com", "+0987654321"])

        return response

    def post(self, request, shop_id, *args, **kwargs):
        require_manage_shop(request.user, shop_id)
        file = request.FILES.get("file")
        if not file:
            return success_response(details="No file uploaded.", code="NO_FILE", data={})

        if not file.name.endswith(".csv"):
            return success_response(details="Please upload a valid CSV file.", code="INVALID_FILE_TYPE", data={})

        try:
            decoded_file = file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            created_count = 0
            errors = []
            import secrets

            for index, row in enumerate(reader, start=1):
                name = row.get("name", "").strip()
                email = row.get("email", "").strip()
                phone = row.get("phone", "").strip()

                if not email:
                    errors.append(f"Row {index}: Email is missing.")
                    continue

                if User.objects.filter(email=email).exists():
                    errors.append(f"Row {index}: User with email {email} already exists.")
                    continue

                user = User.objects.create_user(
                    username=secrets.token_urlsafe(12),
                    email=email,
                    password=secrets.token_urlsafe(12),
                    full_name=name,
                    phone=phone,
                    role=UserRole.USER,
                )
                user.set_unique_username()
                user.save()
                created_count += 1

            data = {"created_count": created_count, "errors": errors}
            return success_response(details=f"Imported {created_count} clients.", code="IMPORT_SUCCESS", data=data)

        except Exception as e:
            return success_response(details=f"Failed to parse CSV: {str(e)}", code="PARSE_ERROR", data={})
