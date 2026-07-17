# Generated manually for PlanFunnelEvent event type expansion

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0010_planfunnelevent'),
    ]

    operations = [
        migrations.AlterField(
            model_name='planfunnelevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('pricing_view', 'بازدید صفحه قیمت\u200cگذاری'),
                    ('checkout_view', 'شروع خرید'),
                    ('upgrade_view', 'بازدید صفحه ارتقا'),
                    ('payment_success', 'پرداخت موفق'),
                    ('payment_failed', 'پرداخت ناموفق'),
                    ('checkout_abandon', 'رها کردن Checkout'),
                ],
                max_length=32,
                verbose_name='نوع رویداد',
            ),
        ),
    ]
