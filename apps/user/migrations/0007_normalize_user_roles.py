from django.db import migrations

ROLE_MAP = {
    "user": "USER",
    "barber": "BARBER",
    "staff": "BARBER",
    "STAFF": "BARBER",
    "manager": "MANAGER",
    "admin": "ADMIN",
    "super_admin": "SUPER_ADMIN",
}


def normalize_roles(apps, schema_editor):
    """Older code saved lowercase roles that never matched the UserRole values."""
    User = apps.get_model("user", "User")
    for old_role, new_role in ROLE_MAP.items():
        User.objects.filter(role=old_role).update(role=new_role)


class Migration(migrations.Migration):
    dependencies = [("user", "0006_alter_user_role")]

    operations = [migrations.RunPython(normalize_roles, migrations.RunPython.noop)]
