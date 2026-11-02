from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payment", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="paymentlog",
            name="method",
            field=models.CharField(
                choices=[
                    ("apple_pay", "Apple Pay"),
                    ("google_pay", "Google Pay"),
                    ("cash", "Cash"),
                    ("card", "Card"),
                    ("mobile_banking", "Mobile Banking"),
                    ("other", "Other"),
                ],
                max_length=20,
            ),
        ),
    ]