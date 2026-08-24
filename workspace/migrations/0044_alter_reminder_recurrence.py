# قبلاً روی سرور production اعمال شده — نگه‌داری برای هم‌ترازی گراف migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0043_crmsavedfilter_listings_scope'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reminder',
            name='recurrence',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'یک\u200cبار'),
                    ('daily', 'روزانه'),
                    ('weekly', 'هفتگی'),
                    ('biweekly', 'دو هفته\u200cای'),
                    ('monthly', 'ماهانه'),
                ],
                default='',
                max_length=20,
                verbose_name='تکرار',
            ),
        ),
    ]
