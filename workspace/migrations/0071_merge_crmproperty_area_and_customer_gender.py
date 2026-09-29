from django.db import migrations


class Migration(migrations.Migration):
    """ادغام شاخه‌های موازی 0070 (متراژ ملک + جنسیت مخاطب)."""

    dependencies = [
        ('workspace', '0070_alter_crmproperty_area'),
        ('workspace', '0070_customer_gender'),
    ]

    operations = []
