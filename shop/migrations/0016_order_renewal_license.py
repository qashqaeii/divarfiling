from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0004_license_bulk_order_fk'),
        ('shop', '0015_licenseplan_features_tagline'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='renewal_license',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='renewal_orders',
                to='licenses.license',
                verbose_name='لایسنس در حال تمدید',
            ),
        ),
    ]
