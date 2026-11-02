from rest_framework import serializers

from .models import PaymentLog


class PaymentLogSerializer(serializers.ModelSerializer):
    booking_code = serializers.CharField(source="booking.booking_code", read_only=True)

    class Meta:
        model = PaymentLog
        fields = ["id", "booking", "booking_code", "amount", "method", "transaction_id", "status", "created_at"]
        read_only_fields = ["id", "created_at"]
