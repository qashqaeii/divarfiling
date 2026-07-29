from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product_hub', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='releasechange',
            name='platform',
            field=models.CharField(
                choices=[
                    ('android', 'اپ اندروید'),
                    ('windows', 'ربات ویندوز'),
                    ('platform', 'پلتفرم و میزکار'),
                    ('all', 'همه پلتفرم‌ها'),
                ],
                default='all',
                help_text='اندروید، ویندوز یا پلتفرم وب/میزکار',
                max_length=20,
                verbose_name='پلتفرم',
            ),
        ),
    ]
