# Generated manually for MobileNotification model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mobile_api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(db_index=True, max_length=40)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField(blank=True)),
                ('deep_link', models.CharField(blank=True, max_length=300)),
                ('data', models.JSONField(blank=True, default=dict)),
                ('is_read', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='mobile_notifications',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'اعلان موبایل',
                'verbose_name_plural': 'اعلان‌های موبایل',
                'ordering': ['-created_at'],
            },
        ),
    ]
