# Index renames — auto-generated on production; folded into main graph via 0060 merge.

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
        migrations.RenameIndex(
            model_name='userlistingactivity',
            new_name='workspace_u_user_id_995697_idx',
            old_name='workspace_u_user_id_6a2f1d_idx',
        ),
        migrations.RenameIndex(
            model_name='userlistingactivity',
            new_name='workspace_u_last_ac_83812a_idx',
            old_name='workspace_u_last_ac_8c4e2a_idx',
        ),
    ]
