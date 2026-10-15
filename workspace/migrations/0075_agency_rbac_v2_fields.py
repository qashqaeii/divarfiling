from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0074_merge_20261008_1039'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmagency',
            name='feature_flags',
            field=models.JSONField(blank=True, default=dict, verbose_name='پرچم‌های قابلیت آژانس'),
        ),
        migrations.AddField(
            model_name='crmagencymember',
            name='permission_overrides',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='کلیدهای مجوز با مقدار boolean — فقط با agency_rbac_v2',
                verbose_name='تنظیم مجوزهای جزئی',
            ),
        ),
    ]
