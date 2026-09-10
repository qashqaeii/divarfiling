"""Allow handover on standalone contracts (no deal)."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0005_merge_20260909_contracts'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contracthandover',
            name='deal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='contract_handovers',
                to='workspace.crmdeal',
                verbose_name='معامله',
            ),
        ),
    ]
