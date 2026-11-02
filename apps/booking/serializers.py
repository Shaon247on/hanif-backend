"""Booking serializers."""

from decimal import Decimal

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.barber.models import Barber
from apps.booking.services import (
    OFFLINE_PAYMENT_METHODS,
    SLOT_UNAVAILABLE_MESSAGE,
    generate_booking_code,
    lock_barber,
    schedule_appointments,
)
from apps.core.access import can_access_shop, can_manage_shop
from apps.service.models import Service
from apps.shop.models import Shop
from apps.user.enums import UserRole
from apps.user.models import User

from .models import Appointment, Booking, ShopReview


class BookingCreateSerializer(serializers.Serializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="customer", required=False, allow_null=True)
    customer = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False, allow_null=True)
    customer_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source="customer", required=False, allow_null=True)
    shop = serializers.PrimaryKeyRelatedField(queryset=Shop.objects.all())
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.all())
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True)
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField()
    payment_method = serializers.ChoiceField(choices=Booking.PAYMENT_METHOD_CHOICES, required=False, allow_null=True)
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal("0.00"))
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal("0.00"), min_value=0)

    def validate(self, attrs):
        user = self.context["request"].user
        shop = attrs["shop"]
        if not can_manage_shop(user, shop.id):
            attrs["discount"] = Decimal("0")

        customer = attrs.get("customer")
        if customer and customer != user and not can_access_shop(user, shop.id):
            raise PermissionDenied("You can only create bookings for yourself.")

        barber = attrs.get("barber")
        appointment_date = attrs.get("appointment_date")
        start_time = attrs.get("start_time")
        services = attrs.get("services", [])

        if barber.shop_id != shop.id:
            raise serializers.ValidationError({"barber": "This barber does not work at the selected shop."})
        if any(service.shop_id != shop.id for service in services):
            raise serializers.ValidationError({"services": "All services must belong to the selected shop."})

        if barber and appointment_date and start_time and services:
            total_duration = sum(s.duration_minutes for s in services)
            from apps.schedule.services import ScheduleService
            is_available = ScheduleService.is_slot_available(
                barber, appointment_date, start_time, total_duration
            )
            if not is_available:
                raise serializers.ValidationError(SLOT_UNAVAILABLE_MESSAGE)

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        from apps.schedule.services import ScheduleService

        user = self.context["request"].user
        customer = validated_data.get("customer") or user
        shop = validated_data["shop"]
        barber = validated_data["barber"]
        services = validated_data["services"]
        appointment_date = validated_data["appointment_date"]
        start_time = validated_data["start_time"]
        payment_method = validated_data.get("payment_method")
        tip_amount = validated_data.get("tip_amount", Decimal("0.00"))
        discount = validated_data.get("discount", Decimal("0.00"))

        # Checked again under the lock: another booking may have taken the slot since validate().
        lock_barber(barber)
        total_duration = sum(service.duration_minutes for service in services)
        if not ScheduleService.is_slot_available(barber, appointment_date, start_time, total_duration):
            raise serializers.ValidationError(SLOT_UNAVAILABLE_MESSAGE)

        total_price = sum(service.price for service in services)
        if discount > total_price + tip_amount:
            raise serializers.ValidationError({"discount": "Discount cannot exceed the booking amount."})

        booking = Booking.objects.create(
            booking_code=generate_booking_code(),
            customer=customer,
            shop=shop,
            total_amount=total_price + tip_amount - discount,
            tip_amount=tip_amount,
            discount_amount=discount,
            payment_method=payment_method,
            payment_status="pending",
            status="pending",
        )
        schedule_appointments(booking, services, barber, appointment_date, start_time)
        return booking


class WalkInCustomerSerializer(serializers.Serializer):
    email = serializers.EmailField()
    full_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="", max_length=20)


class WalkInOrderSerializer(serializers.Serializer):
    """A customer in the shop: identified by account or by email, never through a gateway."""

    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=UserRole.USER), required=False, allow_null=True
    )
    customer = WalkInCustomerSerializer(required=False, allow_null=True)
    shop = serializers.PrimaryKeyRelatedField(queryset=Shop.objects.all())
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.all())
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True, allow_empty=False)
    start_time = serializers.TimeField(required=False, allow_null=True)
    payment_method = serializers.ChoiceField(choices=OFFLINE_PAYMENT_METHODS)
    is_paid = serializers.BooleanField(default=True)
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, default=Decimal("0.00"))
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, default=Decimal("0.00"))

    def validate(self, attrs):
        user = self.context["request"].user
        shop, barber, services = attrs["shop"], attrs["barber"], attrs["services"]

        if not can_access_shop(user, shop.id):
            raise PermissionDenied("You do not have access to this shop.")
        if not (attrs.get("customer_id") or attrs.get("customer")):
            raise serializers.ValidationError({"customer": "Select a customer or enter their email."})
        if barber.shop_id != shop.id:
            raise serializers.ValidationError({"barber": "This barber does not work at the selected shop."})
        if any(service.shop_id != shop.id for service in services):
            raise serializers.ValidationError({"services": "All services must belong to the selected shop."})
        if attrs["discount"] and not can_manage_shop(user, shop.id):
            raise PermissionDenied("Only an admin or manager can give a discount.")
        if attrs["discount"] > sum(service.price for service in services):
            raise serializers.ValidationError({"discount": "Discount cannot exceed the services total."})
        return attrs


class BookingCheckoutSerializer(serializers.Serializer):
    payment_method = serializers.ChoiceField(choices=OFFLINE_PAYMENT_METHODS, required=False)
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    services = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.all(), many=True, required=False, allow_empty=False
    )

    def validate(self, attrs):
        booking = self.context["booking"]
        if attrs.get("discount") and not can_manage_shop(self.context["request"].user, booking.shop_id):
            raise PermissionDenied("Only an admin or manager can give a discount.")
        if any(service.shop_id != booking.shop_id for service in attrs.get("services", [])):
            raise serializers.ValidationError({"services": "All services must belong to this shop."})
        return attrs

class BookingSerializer(serializers.ModelSerializer):
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.all(), write_only=True, required=False)
    shop_details = serializers.SerializerMethodField()
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True, write_only=True, required=False)
    appointment_date = serializers.DateField(write_only=True, required=False)
    start_time = serializers.TimeField(write_only=True, required=False)
    
    appointments_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_code', 'customer', 'shop', 'shop_details', 'total_amount', 'tip_amount', 'discount_amount',
            'payment_method', 'payment_status', 'status', 'source', 'created_at', 'updated_at',
            'barber', 'services', 'appointment_date', 'start_time', 'appointments_details'
        ]
        # Money only changes through checkout, so every payment leaves a PaymentLog
        read_only_fields = [
            'id', 'booking_code', 'customer', 'shop', 'shop_details', 'total_amount', 'tip_amount',
            'discount_amount', 'payment_method', 'payment_status', 'source', 'created_at', 'updated_at',
        ]

    def validate(self, attrs):
        barber = attrs.get("barber")
        if barber and barber.shop_id != self.instance.shop_id:
            raise serializers.ValidationError({"barber": "This barber does not work at this shop."})
        if any(service.shop_id != self.instance.shop_id for service in attrs.get("services", [])):
            raise serializers.ValidationError({"services": "All services must belong to this shop."})
        return attrs

    def get_shop_details(self, obj):
        return {
            "name": obj.shop.name,
            "location": obj.shop.location,
            "phone": obj.shop.phone
        }

    def get_appointments_details(self, obj):
        return [
            {
                "id": a.id,
                "service_id": a.service_id,
                "service_name": a.service.name,
                "barber_id": a.barber_id,
                "barber": {
                    "id": a.barber_id,
                    "name": a.barber.user.full_name or a.barber.user.username,
                    "image": self._get_barber_image(a),
                },
                "appointment_date": a.appointment_date,
                "start_time": a.start_time,
                "end_time": a.end_time,
            }
            for a in obj.appointments.all()
        ]

    def _get_barber_image(self, appointment):
        image_url = appointment.barber.user.image.url if appointment.barber.user.image else None
        request = self.context.get("request")
        return request.build_absolute_uri(image_url) if image_url and request else image_url

    @transaction.atomic
    def update(self, instance, validated_data):
        from apps.schedule.services import ScheduleService

        barber = validated_data.pop("barber", None)
        services = validated_data.pop("services", None)
        appointment_date = validated_data.pop("appointment_date", None)
        start_time = validated_data.pop("start_time", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Only open bookings can be rescheduled, and the new slot must really be free
        if instance.status in ("pending", "confirmed") and any([barber, services, appointment_date, start_time]):
            first_appt = instance.appointments.first()
            if first_appt:
                current_barber = barber or first_appt.barber
                current_date = appointment_date or first_appt.appointment_date
                current_time = start_time or first_appt.start_time
                current_services = services or [a.service for a in instance.appointments.all()]

                lock_barber(current_barber)
                total_duration = sum(service.duration_minutes for service in current_services)
                if not ScheduleService.is_slot_available(
                    current_barber, current_date, current_time, total_duration, exclude_booking=instance
                ):
                    raise serializers.ValidationError(SLOT_UNAVAILABLE_MESSAGE)

                instance.appointments.all().delete()
                total_price = schedule_appointments(
                    instance, current_services, current_barber, current_date, current_time
                )
                instance.total_amount = total_price + instance.tip_amount - instance.discount_amount

        instance.save()
        if instance.status == "completed":
            instance.appointments.exclude(status="cancelled").update(status="completed")
        return instance



class BookingListViewSerializer(serializers.ModelSerializer):
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.all(), write_only=True, required=False)
    services = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), many=True, write_only=True, required=False)
    shop_details = serializers.SerializerMethodField(read_only=True)
    appointments_details = serializers.SerializerMethodField(read_only=True)
    appointment_date = serializers.DateField(write_only=True, required=False)
    start_time = serializers.TimeField(write_only=True, required=False)

    class Meta:
        model = Booking
        fields = [
            'id', 'booking_code', 'customer', 'shop', 'shop_details', 'total_amount', 'tip_amount', 'discount_amount',
            'payment_method', 'payment_status', 'status', 'created_at', 'updated_at',
            'barber', 'services', 'appointment_date', 'start_time', 'appointments_details'
        ]
        read_only_fields = ['id', 'booking_code', 'customer', 'shop', 'shop_details', 'total_amount', 'created_at', 'updated_at']

    def get_shop_details(self, obj):
        return {
            "name": obj.shop.name,
            "location": obj.shop.location,
            "phone": obj.shop.phone
        }

    
    def get_appointments_details(self, obj):
        return [
            {
                "id": a.id,
                "service_id": a.service_id,
                "service_name": a.service.name,
                "barber_id": a.barber_id,
                "barber": {
                    "id": a.barber_id,
                    "name": a.barber.user.full_name or a.barber.user.username,
                    "image": self._get_barber_image(a),
                },
                "appointment_date": a.appointment_date,
                "start_time": a.start_time,
                "end_time": a.end_time,
            }
            for a in obj.appointments.all()
        ]

    def _get_barber_image(self, appointment):
        image_url = appointment.barber.user.image.url if appointment.barber.user.image else None
        request = self.context.get("request")
        return request.build_absolute_uri(image_url) if image_url and request else image_url

    def update(self, instance, validated_data):
        barber = validated_data.pop("barber", None)
        services = validated_data.pop("services", None)
        appointment_date = validated_data.pop("appointment_date", None)
        start_time = validated_data.pop("start_time", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Only allow updating appointments if booking is pending
        if instance.status == "pending" and any([barber, services, appointment_date, start_time]):
            first_appt = instance.appointments.first()
            if first_appt:
                current_barber = barber or first_appt.barber
                current_date = appointment_date or first_appt.appointment_date
                current_time = start_time or first_appt.start_time
                current_services = services or [a.service for a in instance.appointments.all()]
                
                instance.appointments.all().delete()

                current_datetime = timezone.make_aware(datetime.datetime.combine(current_date, current_time))
                total_price = 0
                
                for service in current_services:
                    end_datetime = current_datetime + datetime.timedelta(minutes=service.duration_minutes)
                    Appointment.objects.create(
                        booking=instance,
                        service=service,
                        barber=current_barber,
                        appointment_date=current_datetime.date(),
                        start_time=current_datetime.time(),
                        end_time=end_datetime.time(),
                        price=service.price,
                        status="scheduled",
                    )
                    total_price += service.price
                    current_datetime = end_datetime
                
                instance.total_amount = total_price + instance.tip_amount
        elif 'tip_amount' in validated_data:
            services_total = sum(a.price for a in instance.appointments.all())
            instance.total_amount = services_total + instance.tip_amount

        instance.save()
        return instance

class BookingDetailsSerializer(serializers.ModelSerializer):
    barber = serializers.SerializerMethodField()
    shop = serializers.SerializerMethodField()
    payment_info = serializers.SerializerMethodField()
    appointments_details = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    class Meta:
        model = Booking
        fields = [
            'id', 'booking_code', 'customer', 'shop', 'barber', 'total_amount', 'tip_amount', 'discount_amount',
            'payment_method', 'payment_status', 'payment_info', 'status', 'source', 'created_at', 'updated_at',
            'appointments_details'
        ]
        read_only_fields = fields

    def get_customer(self, obj):
        return {
            "id": obj.customer.id,
            "name": obj.customer.full_name or obj.customer.username,
            "image": obj.customer.image.url if obj.customer.image else None,
        }

    def get_barber(self, obj):
        appointments = obj.appointments.all()
        if appointments.exists():
            barber = appointments.first().barber
            return {
                "id": barber.id,
                "role": barber.role,
                "specialty": barber.specialty,
                "name": barber.user.full_name or barber.user.username,
                "image": self._get_barber_image(barber),
            }
        return None

    def _get_barber_image(self, barber):
        image_url = barber.user.image.url if barber.user.image else None
        request = self.context.get("request")
        return request.build_absolute_uri(image_url) if image_url and request else image_url

    def get_appointments_details(self, obj):
        services = obj.appointments.select_related("service", "barber__user").all()
        services_data = []
        for appointment in services:
            services_data.append({
                "id": appointment.id,
                "service_id": appointment.service_id,
                "service_name": appointment.service.name,
                "price": appointment.price,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "status": appointment.status,
            })
        return [
            {
                "id": appointment.id,
                "services": services_data,
                "barber": {
                    "id": appointment.barber_id,
                    "name": appointment.barber.user.full_name or appointment.barber.user.username,
                    "image": self._get_barber_image(appointment.barber),
                },
                "appointment_date": appointment.appointment_date,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "status": appointment.status,
            }
            for appointment in obj.appointments.select_related("service", "barber__user").all()
        ]

    def get_shop(self, obj):
        return {
            "id": obj.shop.id,
            "name": obj.shop.name,
            "location": obj.shop.location,
            "phone": obj.shop.phone,
        }

    def get_payment_info(self, obj):
        from apps.payment.models import PaymentLog
        payment_log = PaymentLog.objects.filter(booking=obj).order_by('-created_at').first()
        if not payment_log:
            return {
                "payment_created_at": obj.created_at,
                "payment_method": obj.payment_method,
                "payment_status": obj.payment_status,
                "amount": obj.total_amount,
            }
        return {
            "payment_created_at": payment_log.created_at,
            "payment_method": payment_log.method,
            "payment_status": payment_log.status,
            "amount": payment_log.amount,
        }

class ShopReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.username", read_only=True)
    shop_name = serializers.CharField(source="shop.name", read_only=True)
    google_review_link = serializers.CharField(source="shop.google_review_link", read_only=True)

    class Meta:
        model = ShopReview
        fields = [
            "id",
            "shop",
            "shop_name",
            "google_review_link",
            "customer",
            "customer_name",
            "booking",
            "rating",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "shop", "customer", "created_at", "updated_at")

    def validate(self, attrs):
        booking = attrs.get("booking")
        request = self.context.get("request")

        if request and request.user:
            if booking.customer != request.user:
                raise serializers.ValidationError("You can only review your own bookings.")
            attrs["customer"] = request.user
            attrs["shop"] = booking.shop
        return attrs
