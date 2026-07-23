from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0041_academy_video_views'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='matching_tolerance_percent',
            field=models.PositiveSmallIntegerField(
                default=20,
                help_text='حداکثر فاصله مجاز از بازه بودجه و متراژ — ۰ تا ۵۰٪',
                verbose_name='انعطاف‌پذیری تطبیق (٪)',
            ),
        ),
    ]
