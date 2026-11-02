from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("shop", "0005_alter_shop_cover_image_alter_shop_logo_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessHourBreak",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.SmallIntegerField(choices=[(1, "Active"), (0, "Inactive"), (2, "Draft"), (3, "Deleted")], db_index=True, default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                ("business_hour", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="breaks", to="shop.businesshour")),
            ],
            options={"ordering": ["start_time"]},
        ),
    ]