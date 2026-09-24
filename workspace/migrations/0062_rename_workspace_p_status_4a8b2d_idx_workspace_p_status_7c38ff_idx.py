# Auto-generated on production (makemigrations); committed to unify migration graph.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0061_propertyaccessibilityjob'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='propertyaccessibilityjob',
            new_name='workspace_p_status_7c38ff_idx',
            old_name='workspace_p_status_4a8b2d_idx',
        ),
    ]
