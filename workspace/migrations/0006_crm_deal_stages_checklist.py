from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0005_crm_saved_filters'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacesettings',
            name='crm_deal_stages',
            field=models.JSONField(blank=True, default=list, verbose_name='مراحل سفارشی pipeline معامله'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='checklist',
            field=models.JSONField(blank=True, default=list, verbose_name='چک‌لیست مدارک'),
        ),
        migrations.AlterField(
            model_name='crmdeal',
            name='stage',
            field=models.CharField(default='سرنخ', max_length=60, verbose_name='مرحله'),
        ),
    ]
