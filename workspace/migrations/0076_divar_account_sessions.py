# Generated manually for Divar session infrastructure

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0075_agency_rbac_v2_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='DivarContactFeatureConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('singleton_key', models.CharField(default='default', max_length=16, unique=True)),
                (
                    'rollout_mode',
                    models.CharField(
                        choices=[
                            ('disabled', 'غیرفعال برای همه'),
                            ('admin_only', 'فقط Superuser'),
                            ('enabled_for_all', 'فعال برای همه کاربران'),
                        ],
                        db_index=True,
                        default='admin_only',
                        max_length=32,
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'updated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'تنظیمات دریافت شماره از دیوار',
                'verbose_name_plural': 'تنظیمات دریافت شماره از دیوار',
            },
        ),
        migrations.CreateModel(
            name='DivarContactFeatureAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field_name', models.CharField(max_length=64)),
                ('old_value', models.CharField(blank=True, max_length=128)),
                ('new_value', models.CharField(blank=True, max_length=128)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    'changed_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='+',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'لاگ تنظیمات دیوار',
                'verbose_name_plural': 'لاگ تنظیمات دیوار',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DivarAccountSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('divar_phone', models.CharField(db_index=True, max_length=20)),
                ('encrypted_session', models.TextField(blank=True, help_text='SessionStore JSON — Fernet')),
                (
                    'auth_status',
                    models.CharField(
                        choices=[
                            ('pending_otp', 'در انتظار OTP'),
                            ('connected', 'متصل'),
                            ('expired', 'منقضی'),
                            ('captcha_required', 'نیاز به کپچا'),
                            ('disconnected', 'قطع شده'),
                            ('error', 'خطا'),
                        ],
                        db_index=True,
                        default='pending_otp',
                        max_length=32,
                    ),
                ),
                ('hip_status', models.CharField(blank=True, default='', max_length=64)),
                ('connected_at', models.DateTimeField(blank=True, null=True)),
                ('last_health_check_at', models.DateTimeField(blank=True, null=True)),
                ('last_success_at', models.DateTimeField(blank=True, null=True)),
                ('token_expires_at', models.DateTimeField(blank=True, null=True)),
                ('last_refresh_at', models.DateTimeField(blank=True, null=True)),
                ('last_error_code', models.CharField(blank=True, default='', max_length=64)),
                ('last_error_message', models.CharField(blank=True, default='', max_length=500)),
                ('phone_detector_consent', models.BooleanField(db_index=True, default=False)),
                ('phone_detector_consent_at', models.DateTimeField(blank=True, null=True)),
                ('phone_detector_consent_version', models.CharField(blank=True, default='', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='divar_account_sessions',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'نشست حساب دیوار',
                'verbose_name_plural': 'نشست‌های حساب دیوار',
            },
        ),
        migrations.CreateModel(
            name='DivarOtpChallenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('divar_phone', models.CharField(db_index=True, max_length=20)),
                ('encrypted_pending', models.TextField()),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='divar_otp_challenges',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'چالش OTP دیوار',
                'verbose_name_plural': 'چالش‌های OTP دیوار',
            },
        ),
        migrations.CreateModel(
            name='DivarPhoneFetchLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing_token', models.CharField(db_index=True, max_length=100)),
                ('success', models.BooleanField(db_index=True, default=False)),
                ('error_code', models.CharField(blank=True, default='', max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='divar_phone_fetch_logs',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'verbose_name': 'لاگ دریافت شماره دیوار',
                'verbose_name_plural': 'لاگ‌های دریافت شماره دیوار',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='divaraccountsession',
            constraint=models.UniqueConstraint(
                fields=('user', 'divar_phone'),
                name='workspace_divar_session_user_phone_uniq',
            ),
        ),
        migrations.AddIndex(
            model_name='divaraccountsession',
            index=models.Index(fields=['user', 'auth_status'], name='workspace_d_user_id_4f0a91_idx'),
        ),
        migrations.AddConstraint(
            model_name='divarotpchallenge',
            constraint=models.UniqueConstraint(
                fields=('user', 'divar_phone'),
                name='workspace_divar_otp_user_phone_uniq',
            ),
        ),
        migrations.RunPython(
            lambda apps, schema_editor: apps.get_model('workspace', 'DivarContactFeatureConfig').objects.get_or_create(
                singleton_key='default',
                defaults={'rollout_mode': 'admin_only'},
            ),
            migrations.RunPython.noop,
        ),
    ]
