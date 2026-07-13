# Generated manually for ClientAppEvent

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('licenses', '0002_license_activation_seats'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClientAppEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('hardware_fingerprint', models.CharField(db_index=True, max_length=200, verbose_name='شناسه سخت\u200cافزاری')),
                ('event_type', models.CharField(choices=[('first_launch', 'اولین اجرا'), ('app_launch', 'اجرای برنامه')], max_length=32, verbose_name='نوع رویداد')),
                ('platform', models.CharField(choices=[('windows', 'ویندوز')], default='windows', max_length=20, verbose_name='پلتفرم')),
                ('app_version', models.CharField(blank=True, max_length=40, verbose_name='نسخه اپ')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='آدرس IP')),
                ('user_agent', models.TextField(blank=True, verbose_name='User Agent')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ رویداد')),
                ('activation', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='client_events', to='licenses.licenseactivation', verbose_name='اسلات دستگاه')),
                ('license', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_events', to='licenses.license', verbose_name='لایسنس')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='client_app_events', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'رویداد اپ کلاینت',
                'verbose_name_plural': 'رویدادهای اپ کلاینت',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='clientappevent',
            constraint=models.UniqueConstraint(fields=('license', 'hardware_fingerprint', 'event_type'), name='uniq_client_event_per_device'),
        ),
    ]
