# Generated manually — وضعیت granted برای سفارش هدیه کمپین

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0020_card_transfer_sms_tracking'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'در انتظار پرداخت'),
                    ('pending_verification', 'در انتظار تایید پرداخت'),
                    ('paid', 'پرداخت شده'),
                    ('granted', 'اعطای هدیه/کمپین'),
                    ('failed', 'ناموفق'),
                    ('cancelled', 'لغو شده'),
                ],
                default='pending',
                max_length=20,
                verbose_name='وضعیت',
            ),
        ),
    ]
