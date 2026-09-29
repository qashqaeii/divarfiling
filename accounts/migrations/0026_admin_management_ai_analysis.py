from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0025_userprofile_avatar_key'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdminManagementAIAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section', models.CharField(db_index=True, max_length=32, verbose_name='بخش')),
                ('days_key', models.CharField(max_length=8, verbose_name='کلید بازه')),
                ('compare', models.BooleanField(default=False, verbose_name='مقایسه')),
                ('snapshot_fingerprint', models.CharField(max_length=64, verbose_name='Fingerprint')),
                ('analysis_json', models.JSONField(default=dict, verbose_name='خروجی AI')),
                ('generated_at', models.DateTimeField(auto_now=True, verbose_name='زمان تولید')),
                ('provider', models.CharField(blank=True, max_length=30, verbose_name='Provider')),
                ('model', models.CharField(blank=True, max_length=120, verbose_name='مدل')),
                (
                    'generated_by',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='management_ai_analyses',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='تولیدکننده',
                    ),
                ),
            ],
            options={
                'verbose_name': 'تحلیل AI مدیریت',
                'verbose_name_plural': 'تحلیل‌های AI مدیریت',
            },
        ),
        migrations.AddConstraint(
            model_name='adminmanagementaianalysis',
            constraint=models.UniqueConstraint(
                fields=('section', 'days_key', 'compare'),
                name='accounts_mgmt_ai_scope_uniq',
            ),
        ),
    ]
