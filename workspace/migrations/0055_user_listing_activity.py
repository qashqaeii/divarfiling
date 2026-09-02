# UserListingActivity — last meaningful user activity per filing token.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0054_user_listing_suppression'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserListingActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_platform', models.CharField(db_index=True, max_length=30, verbose_name='پلتفرم منبع')),
                ('external_id', models.CharField(db_index=True, max_length=100, verbose_name='شناسه خارجی')),
                ('last_activity_at', models.DateTimeField(verbose_name='آخرین فعالیت')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='listing_activities',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='کاربر',
                    ),
                ),
            ],
            options={
                'verbose_name': 'فعالیت آگهی کاربر',
                'verbose_name_plural': 'فعالیت‌های آگهی کاربر',
                'indexes': [
                    models.Index(fields=['user', 'source_platform', 'external_id'], name='workspace_u_user_id_6a2f1d_idx'),
                    models.Index(fields=['last_activity_at'], name='workspace_u_last_ac_8c4e2a_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('user', 'source_platform', 'external_id'),
                        name='uniq_user_listing_activity',
                    ),
                ],
            },
        ),
    ]
