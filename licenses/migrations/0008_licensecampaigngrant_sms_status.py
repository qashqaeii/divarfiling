# Generated manually — وضعیت پایدار صف پیامک کمپین

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0007_licensecampaigngrant'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensecampaigngrant',
            name='sms_skip_reason',
            field=models.CharField(blank=True, max_length=64, verbose_name='دلیل رد پیامک'),
        ),
        migrations.AddField(
            model_name='licensecampaigngrant',
            name='sms_status',
            field=models.CharField(
                choices=[
                    ('pending', 'در انتظار پیامک'),
                    ('sent', 'ارسال\u200cشده'),
                    ('skipped', 'رد شده'),
                    ('failed', 'ناموفق'),
                ],
                db_index=True,
                default='pending',
                max_length=16,
                verbose_name='وضعیت پیامک',
            ),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('licenses', 'LicenseCampaignGrant').objects.filter(
                sms_sent_at__isnull=False,
            ).update(sms_status='sent'),
            reverse_code=migrations.RunPython.noop,
        ),
    ]
