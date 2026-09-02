# UserListingSuppression — per-user explicit delete intent for Divar filing tokens.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0053_rename_workspace_c_user_id_9c4e1a_idx_workspace_c_user_id_47584f_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserListingSuppression',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_platform', models.CharField(db_index=True, max_length=30, verbose_name='پلتفرم منبع')),
                ('external_id', models.CharField(db_index=True, max_length=100, verbose_name='شناسه خارجی')),
                (
                    'reason',
                    models.CharField(
                        choices=[('user_deleted', 'حذف توسط کاربر')],
                        default='user_deleted',
                        max_length=30,
                        verbose_name='دلیل',
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='listing_suppressions',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'سرکوب آگهی کاربر',
                'verbose_name_plural': 'سرکوب آگهی‌های کاربر',
                'indexes': [
                    models.Index(fields=['user', 'source_platform'], name='workspace_u_user_id_00e876_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('user', 'source_platform', 'external_id'),
                        name='uniq_user_listing_suppression',
                    ),
                ],
            },
        ),
    ]
