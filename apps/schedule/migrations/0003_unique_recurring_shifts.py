from django.db import migrations, models


def consolidate_shifts(apps, schema_editor):
    """
    Older code stored date changes twice and added a new recurring row on every edit.
    Keep the latest recurring row per weekday and move dated shifts into BarberShiftOverride.
    """
    BarberShift = apps.get_model("schedule", "BarberShift")
    BarberShiftOverride = apps.get_model("schedule", "BarberShiftOverride")

    latest_ids = {}
    recurring = BarberShift.objects.filter(shift_date__isnull=True).exclude(day_of_week__isnull=True)
    for shift in recurring.order_by("updated_at", "id"):
        latest_ids[(shift.barber_id, shift.day_of_week)] = shift.id
    recurring.exclude(id__in=latest_ids.values()).delete()

    dated = BarberShift.objects.filter(shift_date__isnull=False)
    for shift in dated.order_by("updated_at", "id"):
        BarberShiftOverride.objects.get_or_create(
            barber_id=shift.barber_id,
            date=shift.shift_date,
            defaults={"start_time": shift.start_time, "end_time": shift.end_time, "is_active": shift.is_active},
        )
    dated.delete()
    BarberShift.objects.filter(shift_date__isnull=True, day_of_week__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("schedule", "0002_barbershiftoverride")]

    operations = [
        migrations.RunPython(consolidate_shifts, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="barbershift",
            constraint=models.UniqueConstraint(
                condition=models.Q(("shift_date__isnull", True)),
                fields=("barber", "day_of_week"),
                name="unique_recurring_barber_shift",
            ),
        ),
    ]
