from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mobile_api', '0005_notification_v2'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileSyncOperation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('op_id', models.CharField(max_length=128)),
                ('entity', models.CharField(blank=True, max_length=40)),
                ('server_id', models.BigIntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('ok', 'موفق'), ('conflict', 'تعارض')], default='ok', max_length=16)),
                ('conflict_reason', models.CharField(blank=True, max_length=300)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mobile_sync_operations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'عملیات Sync موبایل',
                'verbose_name_plural': 'عملیات\u200cهای Sync موبایل',
            },
        ),
        migrations.AddIndex(
            model_name='mobilesyncoperation',
            index=models.Index(fields=['user', 'created_at'], name='mobile_sync_op_user_created'),
        ),
        migrations.AddConstraint(
            model_name='mobilesyncoperation',
            constraint=models.UniqueConstraint(fields=('user', 'op_id'), name='uniq_mobile_sync_op'),
        ),
    ]
