# Index renames for AdvertiserSignalFeedback — auto-generated on production; kept for graph consistency.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0056_advertiser_signal_feedback'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='advertisersignalfeedback',
            new_name='workspace_a_detecto_f212ac_idx',
            old_name='workspace_a_detecto_6a8f2d_idx',
        ),
        migrations.RenameIndex(
            model_name='advertisersignalfeedback',
            new_name='workspace_a_predict_119843_idx',
            old_name='workspace_a_predict_0c4e91_idx',
        ),
    ]
