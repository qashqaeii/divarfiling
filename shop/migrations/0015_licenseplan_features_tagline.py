from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0014_licenseplan_offers_and_order_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='licenseplan',
            name='features',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='لیست متن یا {"text": "...", "icon": "fa-check"} — اگر خالی باشد، ویژگی\u200cهای پیش\u200cفرض نمایش داده می\u200cشود.',
                verbose_name='ویژگی\u200cهای پلن',
            ),
        ),
        migrations.AddField(
            model_name='licenseplan',
            name='tagline',
            field=models.CharField(
                blank=True,
                help_text='زیر عنوان پلن در صفحه خرید — مثلاً «مناسب شروع سریع»',
                max_length=200,
                verbose_name='توضیح کوتاه پلن',
            ),
        ),
    ]
