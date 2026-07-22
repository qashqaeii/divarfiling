from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0015_licenseplan_features_tagline'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licenseplan',
            name='features',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='لیست متن یا آبجکت {"text": "...", "icon": "fa-check"} — در صورت خالی، ویژگی\u200cهای پیش\u200cفرض نمایش داده می\u200cشود.',
                verbose_name='ویژگی\u200cهای پلن',
            ),
        ),
        migrations.AlterField(
            model_name='licenseplan',
            name='tagline',
            field=models.CharField(
                blank=True,
                help_text='زیر عنوان پلن در صفحه خرید — مثلاً «مناسب شروع کار»',
                max_length=200,
                verbose_name='توضیح کوتاه پلن',
            ),
        ),
    ]
