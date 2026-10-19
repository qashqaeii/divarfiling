from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('licenses', '0008_licensecampaigngrant_sms_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='licensecampaigngrant',
            name='welcome_modal_seen_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان مشاهده تبریک خوش‌آمد'),
        ),
        migrations.AddField(
            model_name='licensecampaigngrant',
            name='welcome_tour_started_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان شروع تور پس از هدیه'),
        ),
    ]
