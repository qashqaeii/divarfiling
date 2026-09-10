# Merge parallel 0058 branches: agency invite SMS + CRM deal lost_reason

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0058_agency_invite_sms_metadata'),
        ('workspace', '0058_alter_crmdeal_lost_reason'),
    ]

    operations = []
