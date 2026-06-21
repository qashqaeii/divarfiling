from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0006_payment_card_transfer'),
    ]

    operations = [
        migrations.AlterField(
            model_name='licenseplan',
            name='plan_type',
            field=models.CharField(
                choices=[
                    ('single', 'یک‌سیستمی'),
                    ('multi', 'چندسیستمی'),
                    ('lifetime', 'مادام\u200cالعمر'),
                    ('monthly', 'یک\u200cماهه'),
                    ('quarterly', 'سه\u200cماهه'),
                    ('yearly', 'یک\u200cساله'),
                ],
                max_length=20,
                verbose_name='نوع پلن',
            ),
        ),
    ]
