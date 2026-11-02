from django.db import models
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from apps.barber.models import Barber
from apps.core.access import can_manage_shop
from apps.schedule.models import BarberBreak, BarberShift, BarberShiftOverride, BarberTimeOff
from apps.schedule.services import ScheduleService
from apps.shop.models import (
    BusinessHour,
    BusinessHourBreak,
    BusinessOff,
    ShopBusinessHourOverride,
    ShopBusinessHourOverrideBreak,
)


def validate_breaks(breaks, window_start=None, window_end=None):
    """Breaks must sit inside the working window and must not overlap each other."""
    ordered = sorted(breaks, key=lambda item: item["start_time"])
    for item in ordered:
        if window_start and (item["start_time"] < window_start or item["end_time"] > window_end):
            raise serializers.ValidationError({"breaks": "Breaks must fall within the working hours."})
    for current, following in zip(ordered, ordered[1:]):
        if following["start_time"] < current["end_time"]:
            raise serializers.ValidationError({"breaks": "Breaks cannot overlap each other."})


class TimeRangeInputSerializer(serializers.Serializer):
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    title = serializers.CharField(required=False, allow_blank=True, default="Break")
    is_active = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        if attrs["start_time"] >= attrs["end_time"]:
            raise serializers.ValidationError("End time must be after start time.")
        return attrs


class ShopHoursInputSerializer(serializers.Serializer):
    """Shared rules for recurring hours and date-specific hours."""

    open_time = serializers.TimeField(required=False, allow_null=True)
    close_time = serializers.TimeField(required=False, allow_null=True)
    is_closed = serializers.BooleanField(required=False, default=False)
    breaks = TimeRangeInputSerializer(many=True, required=False)

    def validate(self, attrs):
        if attrs["is_closed"]:
            return attrs
        open_time, close_time = attrs.get("open_time"), attrs.get("close_time")
        if not open_time or not close_time:
            raise serializers.ValidationError("Opening and closing times are required.")
        if open_time >= close_time:
            raise serializers.ValidationError("Closing time must be after opening time.")
        validate_breaks(attrs.get("breaks", []), open_time, close_time)
        return attrs


class RecurringHoursInputSerializer(ShopHoursInputSerializer):
    day_of_week = serializers.ChoiceField(choices=BusinessHour.DAY_CHOICES)


class DateHoursInputSerializer(ShopHoursInputSerializer):
    date = serializers.DateField()


class BarberDateShiftInputSerializer(serializers.Serializer):
    start_time = serializers.TimeField(required=False, allow_null=True)
    end_time = serializers.TimeField(required=False, allow_null=True)
    is_off = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["is_off"]:
            attrs["start_time"] = attrs["end_time"] = None
            return attrs
        start_time, end_time = attrs.get("start_time"), attrs.get("end_time")
        if not start_time or not end_time:
            raise serializers.ValidationError("Duty in and duty out times are required.")
        if start_time >= end_time:
            raise serializers.ValidationError("Duty out must be after duty in.")
        return attrs


class BusinessHourBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessHourBreak
        fields = ["id", "start_time", "end_time"]
        read_only_fields = ["id"]


class BusinessHourSerializer(serializers.ModelSerializer):
    breaks = BusinessHourBreakSerializer(many=True, read_only=True)

    class Meta:
        model = BusinessHour
        fields = ["id", "shop", "day_of_week", "open_time", "close_time", "is_closed", "breaks"]
        read_only_fields = ["id"]


class BusinessOffSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source="shop.name", read_only=True)

    class Meta:
        model = BusinessOff
        fields = [
            "id",
            "shop",
            "shop_name",
            "start_date",
            "end_date",
            "is_full_day",
            "start_time",
            "end_time",
            "reason",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "shop_name", "created_at", "updated_at"]

    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        if current("end_date") < current("start_date"):
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        is_full_day = attrs.get("is_full_day", getattr(self.instance, "is_full_day", True))
        if is_full_day:
            attrs["start_time"] = attrs["end_time"] = None
        elif not current("start_time") or not current("end_time") or current("start_time") >= current("end_time"):
            raise serializers.ValidationError({"end_time": "A partial day off needs a valid start and end time."})
        return attrs


class ShopBusinessHourOverrideBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShopBusinessHourOverrideBreak
        fields = ["id", "start_time", "end_time"]
        read_only_fields = ["id"]


class ShopBusinessHourOverrideSerializer(serializers.ModelSerializer):
    breaks = ShopBusinessHourOverrideBreakSerializer(many=True, read_only=True)

    class Meta:
        model = ShopBusinessHourOverride
        fields = ["id", "shop", "date", "open_time", "close_time", "is_closed", "breaks"]
        read_only_fields = ["id", "shop"]


class BarberShiftSerializer(serializers.ModelSerializer):
    """Recurring weekly shifts. One row per weekday; saving a weekday again updates that row."""

    barber_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BarberShift
        fields = ["id", "barber", "barber_name", "day_of_week", "shift_date", "start_time", "end_time", "is_active"]
        read_only_fields = ["id", "barber_name"]
        validators = []

    def get_barber_name(self, obj):
        if obj.barber and obj.barber.user:
            return obj.barber.user.full_name or obj.barber.user.username
        return ""

    def validate(self, attrs):
        def current(field, default=None):
            return attrs.get(field, getattr(self.instance, field, default))

        if attrs.get("shift_date"):
            raise serializers.ValidationError(
                {"shift_date": "Use the barber schedule endpoint to change a specific date."}
            )

        day_of_week = current("day_of_week")
        if not day_of_week:
            raise serializers.ValidationError({"day_of_week": "day_of_week is required."})
        if not current("is_active", True):
            return attrs

        start_time, end_time = current("start_time"), current("end_time")
        if start_time >= end_time:
            raise serializers.ValidationError({"end_time": "Duty out must be after duty in."})

        hours = BusinessHour.objects.filter(shop=current("barber").shop, day_of_week=day_of_week).first()
        if hours and hours.is_closed:
            raise serializers.ValidationError(f"The shop is closed on {day_of_week.capitalize()}.")
        if hours and hours.open_time and (start_time < hours.open_time or end_time > hours.close_time):
            raise serializers.ValidationError("Staff working hours must stay within the shop's business hours.")
        return attrs

    def create(self, validated_data):
        validated_data.pop("shift_date", None)
        shift, _ = BarberShift.objects.update_or_create(
            barber=validated_data.pop("barber"),
            day_of_week=validated_data.pop("day_of_week"),
            shift_date=None,
            defaults=validated_data,
        )
        return shift


class BarberShiftOverrideSerializer(serializers.ModelSerializer):
    barber_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = BarberShiftOverride
        fields = [
            "id",
            "barber",
            "barber_name",
            "date",
            "start_time",
            "end_time",
            "is_off",
            "is_active",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "barber_name", "created_at", "updated_at"]

    def get_barber_name(self, obj):
        if obj.barber and obj.barber.user:
            return obj.barber.user.full_name or obj.barber.user.username
        return ""


class BarberBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = BarberBreak
        fields = ["id", "barber", "day_of_week", "break_date", "start_time", "end_time", "title", "is_active"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        def current(field):
            return attrs.get(field, getattr(self.instance, field, None))

        barber = current("barber")
        day_of_week, break_date = current("day_of_week"), current("break_date")
        if bool(day_of_week) == bool(break_date):
            raise serializers.ValidationError("Choose either a weekday or a specific date for the break.")
        if current("start_time") >= current("end_time"):
            raise serializers.ValidationError({"end_time": "Break end must be after break start."})

        window_start = window_end = None
        if break_date:
            schedule = ScheduleService.get_barber_schedule(barber, break_date)
            window_start, window_end = schedule["start_time"], schedule["end_time"]
            siblings = BarberBreak.objects.filter(barber=barber, break_date=break_date)
        else:
            shift = BarberShift.objects.filter(
                barber=barber, day_of_week=day_of_week, shift_date__isnull=True, is_active=True
            ).first()
            if shift:
                window_start, window_end = shift.start_time, shift.end_time
            siblings = BarberBreak.objects.filter(barber=barber, day_of_week=day_of_week, break_date__isnull=True)

        if self.instance:
            siblings = siblings.exclude(pk=self.instance.pk)
        breaks = [{"start_time": item.start_time, "end_time": item.end_time} for item in siblings]
        breaks.append({"start_time": current("start_time"), "end_time": current("end_time")})
        validate_breaks(breaks, window_start, window_end)
        return attrs


class BarberTimeOffSerializer(serializers.ModelSerializer):
    barber_name = serializers.SerializerMethodField(read_only=True)
    barber_image = serializers.SerializerMethodField(read_only=True)
    barber = serializers.PrimaryKeyRelatedField(queryset=Barber.objects.all(), required=False)
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(
        choices=BarberTimeOff.STATUS_CHOICES, required=False
    )

    class Meta:
        model = BarberTimeOff
        fields = [
            "id",
            "barber",
            "barber_name",
            "barber_image",
            "start_date",
            "end_date",
            "is_full_day",
            "start_time",
            "end_time",
            "reason",
            "status",
            "reviewed_by",
        ]
        read_only_fields = ["id", "reviewed_by"]

    def get_barber_name(self, obj):
        if obj.barber and obj.barber.user:
            return obj.barber.user.full_name or obj.barber.user.username
        return ""

    def get_barber_image(self, obj):
        image = obj.barber.user.image if obj.barber and obj.barber.user else None
        if not image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.url) if request else image.url

    def to_internal_value(self, data):
        if isinstance(data, dict):
            mutable_data = data.copy()
            if "date" in mutable_data and "start_date" not in mutable_data:
                mutable_data["start_date"] = mutable_data["date"]
            if "start_date" in mutable_data and "end_date" not in mutable_data:
                mutable_data["end_date"] = mutable_data["start_date"]
            for key in ["barber_id", "staff", "staff_id", "user", "user_id"]:
                if key in mutable_data and "barber" not in mutable_data:
                    val = mutable_data[key]
                    barber_obj = Barber.objects.filter(models.Q(pk=val) | models.Q(user__id=val)).first()
                    if barber_obj:
                        mutable_data["barber"] = barber_obj.id
            data = mutable_data
        return super().to_internal_value(data)

    def validate(self, attrs):
        request = self.context.get("request")

        if self.instance:
            barber = attrs.get("barber", self.instance.barber)
        else:
            if "barber" not in attrs:
                if request and hasattr(request.user, "barber_profile"):
                    attrs["barber"] = request.user.barber_profile
                elif request and Barber.objects.filter(user=request.user).exists():
                    attrs["barber"] = Barber.objects.filter(user=request.user).first()
                else:
                    raise serializers.ValidationError({"barber": "Barber is required."})

            if "start_date" not in attrs:
                raise serializers.ValidationError({"start_date": "start_date or date is required."})

            if "end_date" not in attrs:
                attrs["end_date"] = attrs["start_date"]

            barber = attrs["barber"]

        self._validate_period(attrs, barber)

        if request and request.user and request.user.is_authenticated:
            if can_manage_shop(request.user, barber.shop_id):
                if not self.instance and "status" not in attrs:
                    attrs["status"] = "approved"
                    attrs["reviewed_by"] = request.user
            else:
                # Barbers can only request their own time off; approving it stays with management.
                if barber.user_id != request.user.id:
                    raise PermissionDenied("You can only request time off for yourself.")
                attrs["status"] = "pending"
                attrs.pop("reviewed_by", None)

        return attrs

    def _validate_period(self, attrs, barber):
        def current(field, default=None):
            return attrs.get(field, getattr(self.instance, field, default))

        start_date, end_date = current("start_date"), current("end_date")
        if end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})

        is_full_day = current("is_full_day", True)
        start_time, end_time = current("start_time"), current("end_time")
        if is_full_day:
            attrs["start_time"] = attrs["end_time"] = None
        else:
            if not start_time or not end_time:
                raise serializers.ValidationError({"start_time": "Hourly time off needs a start and end time."})
            if start_time >= end_time:
                raise serializers.ValidationError({"end_time": "End time must be after start time."})

        others = BarberTimeOff.objects.filter(
            barber=barber, start_date__lte=end_date, end_date__gte=start_date, status__in=["pending", "approved"]
        )
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        for other in others:
            if (
                is_full_day
                or other.is_full_day
                or max(start_time, other.start_time) < min(end_time, other.end_time)
            ):
                raise serializers.ValidationError("This time off overlaps an existing time off record.")
