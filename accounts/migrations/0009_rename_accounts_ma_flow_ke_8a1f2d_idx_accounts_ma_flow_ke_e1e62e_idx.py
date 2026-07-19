# Index rename — هم‌راستا با migration خودکار Django روی production

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_test_provider_accepted_action'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='marketingautomationactionlog',
            new_name='accounts_ma_flow_ke_e1e62e_idx',
            old_name='accounts_ma_flow_ke_8a1f2d_idx',
        ),
    ]
