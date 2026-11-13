from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0030_userdiscountissuance_unique_policy'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='activity_province',
            field=models.CharField(blank=True, max_length=80, verbose_name='استان فعالیت'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='activity_city',
            field=models.CharField(blank=True, max_length=100, verbose_name='شهر فعالیت'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='activity_districts',
            field=models.JSONField(blank=True, default=list, verbose_name='مناطق تخصصی'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='activity_neighborhoods',
            field=models.JSONField(blank=True, default=list, verbose_name='محله‌های تخصصی'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='years_experience',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='سال‌های تجربه'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='expertise_areas',
            field=models.JSONField(blank=True, default=list, verbose_name='حوزه‌های تخصص'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='property_specialties',
            field=models.JSONField(blank=True, default=list, verbose_name='انواع ملک'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='job_role',
            field=models.CharField(blank=True, max_length=32, verbose_name='نقش شغلی'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='office_agency_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='نام بنگاه'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='office_agency_city',
            field=models.CharField(blank=True, max_length=100, verbose_name='شهر دفتر'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='office_agency_address',
            field=models.TextField(blank=True, verbose_name='آدرس دفتر'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='office_agency_phone',
            field=models.CharField(blank=True, max_length=20, verbose_name='تلفن دفتر'),
        ),
    ]
