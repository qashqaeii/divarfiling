from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0014_alter_customer_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='advertiser_signal',
            field=models.CharField(
                blank=True,
                db_index=True,
                default='',
                max_length=32,
                verbose_name='سیگنال آگهی‌دهنده',
            ),
        ),
    ]
