from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0003_clientappevent'),
        ('shop', '0014_licenseplan_offers_and_order_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='sequence',
            field=models.PositiveSmallIntegerField(default=1, verbose_name='شماره در سفارش'),
        ),
        migrations.AlterField(
            model_name='license',
            name='order',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='licenses',
                to='shop.order',
                verbose_name='سفارش',
            ),
        ),
        migrations.AddConstraint(
            model_name='license',
            constraint=models.UniqueConstraint(
                fields=('order', 'sequence'),
                name='uniq_license_order_sequence',
            ),
        ),
    ]
