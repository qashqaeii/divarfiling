# Generated manually for configurable public approx radius

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0034_crmproperty_tenant_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='listingpublicshare',
            name='approximate_location_radius_m',
            field=models.PositiveIntegerField(
                default=500,
                help_text='شعاع دایره تقریبی در صفحه عمومی؛ بین ۱۰ تا ۵۰۰ متر.',
                verbose_name='شعاع موقعیت تقریبی (متر)',
            ),
        ),
        migrations.AddField(
            model_name='crmpropertypublicshare',
            name='approximate_location_radius_m',
            field=models.PositiveIntegerField(
                default=500,
                help_text='شعاع دایره تقریبی در صفحه عمومی؛ بین ۱۰ تا ۵۰۰ متر.',
                verbose_name='شعاع موقعیت تقریبی (متر)',
            ),
        ),
    ]
