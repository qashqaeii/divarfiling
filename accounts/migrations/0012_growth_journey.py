# Generated manually for Growth Journey pipeline

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0011_lead_acquisition_center'),
    ]

    operations = [
        migrations.CreateModel(
            name='GrowthJourney',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_normalized', models.CharField(db_index=True, max_length=20, unique=True)),
                ('stage', models.CharField(
                    choices=[
                        ('cold_lead', 'سرنخ سرد'),
                        ('engaged', 'تعامل‌دار'),
                        ('registered', 'ثبت‌نام‌شده'),
                        ('activated', 'فعال‌شده'),
                        ('nurture_unpaid', 'پیگیری بدون خرید'),
                        ('pending_checkout', 'خرید معلق'),
                        ('customer', 'مشتری'),
                        ('expiring_soon', 'نزدیک انقضا'),
                        ('renewed', 'تمدیدشده'),
                        ('churn_risk', 'ریسک ریزش'),
                        ('suppressed', 'مسدود'),
                    ],
                    db_index=True,
                    default='cold_lead',
                    max_length=24,
                )),
                ('stage_entered_at', models.DateTimeField(auto_now_add=True)),
                ('source', models.CharField(
                    choices=[
                        ('acquisition', 'جذب سرنخ'),
                        ('organic', 'ارگانیک'),
                        ('existing_user', 'کاربر موجود'),
                    ],
                    db_index=True,
                    default='acquisition',
                    max_length=16,
                )),
                ('last_touch_at', models.DateTimeField(blank=True, null=True)),
                ('suppressed', models.BooleanField(db_index=True, default=False)),
                ('nurture_paused', models.BooleanField(db_index=True, default=False)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lead', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='growth_journeys',
                    to='accounts.marketinglead',
                )),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='growth_journeys',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'سفر رشد',
                'verbose_name_plural': 'سفرهای رشد',
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='GrowthJourneyEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage_from', models.CharField(blank=True, max_length=24)),
                ('stage_to', models.CharField(db_index=True, max_length=24)),
                ('event_type', models.CharField(db_index=True, max_length=48)),
                ('ref_model', models.CharField(blank=True, max_length=64)),
                ('ref_id', models.CharField(blank=True, max_length=64)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('journey', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='events',
                    to='accounts.growthjourney',
                )),
            ],
            options={
                'verbose_name': 'رویداد سفر رشد',
                'verbose_name_plural': 'رویدادهای سفر رشد',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='growthjourney',
            index=models.Index(fields=['stage', '-stage_entered_at'], name='accounts_gr_stage_7a1c2d_idx'),
        ),
        migrations.AddIndex(
            model_name='growthjourney',
            index=models.Index(fields=['suppressed', 'nurture_paused', 'stage'], name='accounts_gr_suppres_4b8e1f_idx'),
        ),
        migrations.AddIndex(
            model_name='growthjourneyevent',
            index=models.Index(fields=['journey', '-created_at'], name='accounts_gr_journey_9c2a11_idx'),
        ),
        migrations.AddIndex(
            model_name='growthjourneyevent',
            index=models.Index(fields=['event_type', '-created_at'], name='accounts_gr_event_t_3d4e22_idx'),
        ),
    ]
