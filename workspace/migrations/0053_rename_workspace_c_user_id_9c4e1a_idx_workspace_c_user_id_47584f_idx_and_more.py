# Index renames for CRMDeal / CRMDealFollowUp — may already exist on some production DBs.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0052_crmdeal_next_action_followup'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='crmdeal',
            new_name='workspace_c_user_id_47584f_idx',
            old_name='workspace_c_user_id_9c4e1a_idx',
        ),
        migrations.RenameIndex(
            model_name='crmdealfollowup',
            new_name='workspace_c_deal_id_7cfb0d_idx',
            old_name='workspace_c_deal_id_6a8f2d_idx',
        ),
    ]
