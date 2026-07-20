from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0037_crmproperty_nearby_pois'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmpropertypublicshare',
            name='show_nearby_pois',
            field=models.BooleanField(
                default=False,
                help_text='نمایش فاصله تا مترو، مسجد، بیمارستان و … در صفحه عمومی (نیاز به محاسبه قبلی)',
                verbose_name='نمایش دسترسی‌های اطراف',
            ),
        ),
    ]
