from django.db import migrations


class Migration(migrations.Migration):
    """ادغام شاخهٔ reminder recurrence (سرور) با lease_deadline + زونکن (main)."""

    dependencies = [
        ('workspace', '0044_alter_reminder_recurrence'),
        ('workspace', '0045_crmpropertyfolder'),
    ]

    operations = []
