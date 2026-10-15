# Generated manually for weekly trial campaign

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0027_phone_detector_extraction_line'),
        ('licenses', '0006_agency_entitlement_phase1'),
        ('shop', '0020_card_transfer_sms_tracking'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LicenseCampaignGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('campaign_key', models.CharField(db_index=True, max_length=64, verbose_name='شناسه کمپین')),
                (
                    'status',
                    models.CharField(
                        choices=[('granted', 'فعال\u200cشده'), ('failed', 'خطا'), ('skipped', 'رد شده')],
                        db_index=True,
                        default='granted',
                        max_length=16,
                        verbose_name='وضعیت',
                    ),
                ),
                ('skip_reason', models.CharField(blank=True, max_length=64, verbose_name='دلیل رد')),
                ('error_message', models.CharField(blank=True, max_length=500, verbose_name='پیام خطا')),
                ('granted_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان اعطا')),
                ('expires_at', models.DateTimeField(blank=True, null=True, verbose_name='انقضا')),
                ('sms_sent_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان پیامک')),
                ('metadata', models.JSONField(blank=True, default=dict, verbose_name='متادیتا')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='ایجاد')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='به\u200cروزرسانی')),
                (
                    'license',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='campaign_grants',
                        to='licenses.license',
                        verbose_name='لایسنس',
                    ),
                ),
                (
                    'order',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='campaign_grants',
                        to='shop.order',
                        verbose_name='سفارش هدیه',
                    ),
                ),
                (
                    'sms_log',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='license_campaign_grants',
                        to='accounts.smsmessagelog',
                        verbose_name='لاگ پیامک',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='license_campaign_grants',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'هدیه کمپین لایسنس',
                'verbose_name_plural': 'هدایای کمپین لایسنس',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='licensecampaigngrant',
            index=models.Index(fields=['campaign_key', 'status'], name='licenses_li_campaig_6e2f8d_idx'),
        ),
        migrations.AddConstraint(
            model_name='licensecampaigngrant',
            constraint=models.UniqueConstraint(
                fields=('user', 'campaign_key'),
                name='uniq_license_campaign_grant_user_key',
            ),
        ),
    ]
