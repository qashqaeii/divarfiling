# Generated manually for CRMProperty.feature_data

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0035_share_approximate_location_radius'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='feature_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='کلیدهای فارسی هم‌تراز با دادهٔ آگهی (جنس کف، گرمایش، …)',
                verbose_name='ویژگی‌های تفصیلی',
            ),
        ),
    ]
