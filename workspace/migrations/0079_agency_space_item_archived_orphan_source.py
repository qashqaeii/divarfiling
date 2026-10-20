# Agency Space — allow archived items without live source (provenance / copy history)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0078_divar_pd_sync_block'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='agencyspaceitem',
            name='agency_space_item_one_source',
        ),
        migrations.AddConstraint(
            model_name='agencyspaceitem',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('customer__isnull', True), ('property__isnull', False)),
                    models.Q(('customer__isnull', False), ('property__isnull', True)),
                    models.Q(
                        ('status', 'archived'),
                        ('customer__isnull', True),
                        ('property__isnull', True),
                    ),
                    _connector='OR',
                ),
                name='agency_space_item_one_source',
            ),
        ),
    ]
