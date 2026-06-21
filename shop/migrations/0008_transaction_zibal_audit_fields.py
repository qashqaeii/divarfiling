from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0007_licenseplan_quarterly_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='transaction',
            name='gateway_result_code',
            field=models.IntegerField(blank=True, null=True, verbose_name='کد نتیجه درگاه'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='gateway_message',
            field=models.CharField(blank=True, max_length=255, verbose_name='پیام درگاه'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='callback_payload',
            field=models.JSONField(blank=True, default=dict, verbose_name='داده callback'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='verify_payload',
            field=models.JSONField(blank=True, default=dict, verbose_name='پاسخ verify'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='paid_amount_rial',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='مبلغ پرداخت‌شده (ریال)'),
        ),
        migrations.AddField(
            model_name='transaction',
            name='card_number_masked',
            field=models.CharField(blank=True, max_length=32, verbose_name='شماره کارت (ماسک‌شده)'),
        ),
    ]
