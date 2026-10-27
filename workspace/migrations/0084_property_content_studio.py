from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0083_customer_archive_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='workspacesettings',
            name='content_studio_defaults',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='برند، رنگ و تنظیمات نمایش پیش‌فرض برای پوستر و محتوای تبلیغاتی.',
                verbose_name='پیش‌فرض استودیو محتوای ملک',
            ),
        ),
        migrations.CreateModel(
            name='CRMPropertyContentStudioDraft',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payload', models.JSONField(blank=True, default=dict, verbose_name='داده پیش‌نویس')),
                (
                    'property_fingerprint',
                    models.CharField(
                        blank=True,
                        default='',
                        max_length=64,
                        verbose_name='نگاشت وضعیت ملک',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'property',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='content_studio_drafts',
                        to='workspace.crmproperty',
                        verbose_name='ملک',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='property_content_studio_drafts',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'پیش‌نویس استودیو محتوا',
                'verbose_name_plural': 'پیش‌نویس‌های استودیو محتوا',
                'indexes': [models.Index(fields=['user', 'updated_at'], name='workspace_c_user_id_8f1a2b_idx')],
            },
        ),
        migrations.AddConstraint(
            model_name='crmpropertycontentstudiodraft',
            constraint=models.UniqueConstraint(
                fields=('property', 'user'),
                name='uniq_content_studio_draft_property_user',
            ),
        ),
    ]
