from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0036_crmproperty_feature_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='nearby_pois',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='نزدیک‌ترین POIها بر اساس مختصات — با درخواست کاربر پر می‌شود',
                verbose_name='امکانات اطراف',
            ),
        ),
    ]
