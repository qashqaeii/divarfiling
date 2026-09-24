# Merges production index-rename branch with Agency Space migrations.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            'workspace',
            '0062_rename_workspace_p_status_4a8b2d_idx_workspace_p_status_7c38ff_idx',
        ),
        ('workspace', '0064_agency_space_copy_hardening'),
    ]

    operations = []
