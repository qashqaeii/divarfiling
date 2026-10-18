import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0077_divar_session_coordination'),
    ]

    operations = [
        migrations.AddField(
            model_name='divaraccountsession',
            name='captcha_post_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.CreateModel(
            name='DivarPdSessionFileSyncBlock',
            fields=[
                ('phone', models.CharField(db_index=True, max_length=20, unique=True)),
                (
                    'reason',
                    models.CharField(
                        choices=[
                            ('unlinked', 'حذف ارتباط'),
                            ('disconnected', 'قطع اتصال'),
                            ('invalid', 'نشست نامعتبر'),
                        ],
                        default='unlinked',
                        max_length=32,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                (
                    'session',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pd_sync_blocks',
                        to='workspace.divaraccountsession',
                    ),
                ),
            ],
            options={
                'verbose_name': 'مسدودیت sync فایل PD',
                'verbose_name_plural': 'مسدودیت‌های sync فایل PD',
            },
        ),
    ]
