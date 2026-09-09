"""قرارداد بدون معامله — deal اختیاری با SET_NULL."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_contract_ownership(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    for contract in Contract.objects.select_related('deal').iterator():
        deal = contract.deal
        if not deal:
            continue
        updates = []
        if not contract.user_id and deal.user_id:
            contract.user_id = deal.user_id
            updates.append('user_id')
        if not contract.agency_id and deal.agency_id:
            contract.agency_id = deal.agency_id
            updates.append('agency_id')
        if updates:
            contract.save(update_fields=updates)


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0003_phase3_handover_wizard'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contract',
            name='deal',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='digital_contracts',
                to='workspace.crmdeal',
                verbose_name='معامله',
            ),
        ),
        migrations.RunPython(backfill_contract_ownership, migrations.RunPython.noop),
    ]
