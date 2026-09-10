# Merge parallel branches: production index rename (0057_rename) + agency/lost_reason (0059).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            'workspace',
            '0057_rename_workspace_a_detecto_6a8f2d_idx_workspace_a_detecto_f212ac_idx_and_more',
        ),
        ('workspace', '0059_merge_agency_and_crmdeal_lost_reason'),
    ]

    operations = []
