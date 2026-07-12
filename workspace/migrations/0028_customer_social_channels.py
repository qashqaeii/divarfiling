from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0027_share_approximate_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='social_links',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='آیدی یا شماره در تلگرام، اینستاگرام و سایر شبکه‌ها',
                verbose_name='شناسه شبکه‌های اجتماعی',
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='active_channels',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='لیست شبکه‌هایی که مخاطب در آن‌ها فعال است',
                verbose_name='کانال‌های پیام‌رسانی فعال',
            ),
        ),
    ]
