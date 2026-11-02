from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0003_booking_google_event_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="booking",
            name="discount_amount",
            field=models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
        ),
    ]