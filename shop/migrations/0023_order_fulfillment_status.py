from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0022_orderrenewalitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='fulfillment_status',
            field=models.CharField(
                choices=[
                    ('complete', 'تکمیل‌شده'),
                    ('pending', 'در انتظار اعمال'),
                    ('partial', 'ناقص'),
                    ('failed', 'ناموفق'),
                ],
                db_index=True,
                default='complete',
                max_length=16,
                verbose_name='وضعیت تکمیل لایسنس/تمدید',
            ),
        ),
        migrations.AddField(
            model_name='order',
            name='fulfillment_error',
            field=models.CharField(blank=True, max_length=500, verbose_name='آخرین خطای تکمیل'),
        ),
        migrations.AddField(
            model_name='order',
            name='fulfillment_checked_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='آخرین بررسی تکمیل'),
        ),
    ]
