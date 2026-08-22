# Generated manually for Notification System V2
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mobile_api', '0004_mobile_cloud_extraction_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='mobiledevice',
            name='is_active',
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name='mobilenotification',
            name='dedup_key',
            field=models.CharField(blank=True, db_index=True, max_length=80),
        ),
        migrations.AddField(
            model_name='mobilenotification',
            name='push_status',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddIndex(
            model_name='mobilenotification',
            index=models.Index(fields=['user', 'dedup_key'], name='mobile_notif_user_dedup'),
        ),
        migrations.CreateModel(
            name='MobileNotificationBroadcast',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='عنوان')),
                ('body', models.TextField(verbose_name='متن')),
                ('notification_type', models.CharField(default='announcement', max_length=40, verbose_name='نوع')),
                ('deep_link', models.CharField(blank=True, default='divarfiling://notifications', max_length=300, verbose_name='مقصد')),
                ('priority', models.CharField(default='default', max_length=20, verbose_name='اولویت')),
                ('target', models.CharField(choices=[('all', 'همه کاربران موبایل'), ('licensed', 'دارای لایسنس فعال'), ('unlicensed', 'بدون لایسنس فعال'), ('expiring', 'لایسنس در حال انقضا'), ('selected', 'کاربران انتخاب‌شده')], default='all', max_length=20, verbose_name='مخاطب')),
                ('scheduled_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='زمان ارسال')),
                ('status', models.CharField(choices=[('draft', 'پیش‌نویس'), ('scheduled', 'زمان‌بندی‌شده'), ('sending', 'در حال ارسال'), ('sent', 'ارسال شد'), ('partial', 'ارسال ناقص'), ('failed', 'ناموفق')], db_index=True, default='draft', max_length=20, verbose_name='وضعیت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('target_user_count', models.PositiveIntegerField(default=0)),
                ('target_device_count', models.PositiveIntegerField(default=0)),
                ('success_count', models.PositiveIntegerField(default=0)),
                ('fail_count', models.PositiveIntegerField(default=0)),
                ('last_error', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_mobile_broadcasts', to=settings.AUTH_USER_MODEL, verbose_name='ایجادکننده')),
                ('selected_users', models.ManyToManyField(blank=True, related_name='mobile_notification_broadcasts', to=settings.AUTH_USER_MODEL, verbose_name='کاربران انتخاب‌شده')),
            ],
            options={
                'verbose_name': 'ارسال اعلان گروهی',
                'verbose_name_plural': 'ارسال‌های اعلان گروهی',
                'ordering': ['-created_at'],
                'permissions': [('send_broadcast', 'ارسال اعلان گروهی موبایل')],
            },
        ),
    ]
