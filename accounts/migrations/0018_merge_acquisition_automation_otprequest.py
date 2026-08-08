# Merge parallel 0017 branches: acquisition automation + OtpRequest purpose choices.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0017_acquisition_automation"),
        ("accounts", "0017_alter_otprequest_purpose"),
    ]

    operations = []
