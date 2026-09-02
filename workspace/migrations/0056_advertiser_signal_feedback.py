# Generated manually for AdvertiserSignalFeedback

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0055_user_listing_activity'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvertiserSignalFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing_token', models.CharField(db_index=True, max_length=100, verbose_name='شناسه آگهی')),
                ('predicted_classification', models.CharField(max_length=32, verbose_name='تشخیص سیستم')),
                ('detector_version', models.PositiveSmallIntegerField(default=2, verbose_name='نسخه تشخیص')),
                ('feedback', models.CharField(choices=[('correct', 'درست'), ('incorrect', 'اشتباه')], max_length=16, verbose_name='بازخورد')),
                ('user_correction', models.CharField(blank=True, choices=[('genuine_personal', 'مالک واقعی'), ('disguised_consultant', 'مشاور پنهان'), ('consultant', 'مشاور')], default='', max_length=32, verbose_name='اصلاح کاربر')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='آخرین به‌روزرسانی')),
                ('listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='advertiser_feedbacks', to='workspace.listing', verbose_name='آگهی')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='advertiser_signal_feedbacks', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'بازخورد تشخیص آگهی‌دهنده',
                'verbose_name_plural': 'بازخورد تشخیص آگهی‌دهنده',
            },
        ),
        migrations.AddIndex(
            model_name='advertisersignalfeedback',
            index=models.Index(fields=['detector_version', 'feedback'], name='workspace_a_detecto_6a8f2d_idx'),
        ),
        migrations.AddIndex(
            model_name='advertisersignalfeedback',
            index=models.Index(fields=['predicted_classification', 'feedback'], name='workspace_a_predict_0c4e91_idx'),
        ),
        migrations.AddConstraint(
            model_name='advertisersignalfeedback',
            constraint=models.UniqueConstraint(fields=('user', 'listing', 'detector_version'), name='uniq_advertiser_feedback_per_version'),
        ),
    ]
