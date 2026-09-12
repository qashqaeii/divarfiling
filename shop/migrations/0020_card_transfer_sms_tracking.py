from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0019_user_dismissed_notice'),
    ]

    operations = [
        migrations.AddField(
            model_name='cardtransfersubmission',
            name='admin_sms_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='زمان پیامک اطلاع‌رسانی به مدیر',
            ),
        ),
        migrations.AddField(
            model_name='cardtransfersubmission',
            name='customer_sms_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='زمان پیامک تأیید به کاربر',
            ),
        ),
        migrations.AddField(
            model_name='cardtransfersubmission',
            name='customer_rejection_sms_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='زمان پیامک رد به کاربر',
            ),
        ),
    ]
