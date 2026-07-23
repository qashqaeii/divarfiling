# Generated manually — sync help_text with model (ریال)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_lead_acquisition_center'),
    ]

    operations = [
        migrations.AlterField(
            model_name='campaignmessage',
            name='sms_cost_snapshot',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='هزینه پیامک به‌ریال در لحظه ارسال (بر اساس تعداد بخش × تعرفه)',
                null=True,
            ),
        ),
    ]
