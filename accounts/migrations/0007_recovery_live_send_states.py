# Phase 2.2 — live send states + sms_log FK

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_pending_recovery_automation'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketingautomationactionlog',
            name='provider_message_id',
            field=models.CharField(blank=True, max_length=128, verbose_name='شناسه Provider'),
        ),
        migrations.AddField(
            model_name='marketingautomationactionlog',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='به\u200cروزرسانی'),
        ),
        migrations.AddField(
            model_name='marketingautomationactionlog',
            name='sms_log',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='recovery_actions',
                to='accounts.smsmessagelog',
                verbose_name='لاگ پیامک',
            ),
        ),
        migrations.AlterField(
            model_name='marketingautomationactionlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('would_send', 'Would Send'),
                    ('send_requested', 'Send Requested'),
                    ('provider_accepted', 'Provider Accepted'),
                    ('delivered', 'Delivered'),
                    ('sent', 'Sent (legacy)'),
                    ('failed', 'Failed'),
                    ('suppressed', 'Suppressed'),
                    ('cancelled', 'Cancelled'),
                ],
                db_index=True,
                default='would_send',
                max_length=20,
                verbose_name='اقدام',
            ),
        ),
    ]
