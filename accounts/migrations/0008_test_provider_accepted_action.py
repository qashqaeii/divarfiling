# فاز ۲.۲.۱ — test-only بدون Send Guard

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_recovery_live_send_states'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketingautomationactionlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('would_send', 'Would Send'),
                    ('send_requested', 'Send Requested'),
                    ('provider_accepted', 'Provider Accepted'),
                    ('test_provider_accepted', 'Test Provider Accepted'),
                    ('delivered', 'Delivered'),
                    ('sent', 'Sent (legacy)'),
                    ('failed', 'Failed'),
                    ('suppressed', 'Suppressed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='would_send',
                max_length=24,
                verbose_name='اقدام',
            ),
        ),
    ]
