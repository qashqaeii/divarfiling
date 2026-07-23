# Merge leaf nodes: growth_journey + sms_cost_snapshot alter

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0012_alter_campaignmessage_sms_cost_snapshot'),
        ('accounts', '0012_growth_journey'),
    ]

    operations = []
