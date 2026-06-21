# Generated manually for multi-system license seats

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('licenses', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='licenseactivation',
            options={
                'ordering': ['activated_at', 'pk'],
                'verbose_name': 'اسلات لایسنس',
                'verbose_name_plural': 'اسلات‌های لایسنس',
            },
        ),
        migrations.AddField(
            model_name='licenseactivation',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاریخ تخصیص'),
        ),
        migrations.AddField(
            model_name='licenseactivation',
            name='assigned_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='license_seats_assigned',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تخصیص توسط',
            ),
        ),
        migrations.AddField(
            model_name='licenseactivation',
            name='assigned_user',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='license_seat_assignments',
                to=settings.AUTH_USER_MODEL,
                verbose_name='عضو تیم',
            ),
        ),
        migrations.AddField(
            model_name='licenseactivation',
            name='label',
            field=models.CharField(blank=True, max_length=80, verbose_name='نام سیستم'),
        ),
        migrations.AddField(
            model_name='licenseactivation',
            name='notes',
            field=models.CharField(blank=True, max_length=300, verbose_name='یادداشت'),
        ),
        migrations.AlterField(
            model_name='licenseactivation',
            name='activated_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت'),
        ),
        migrations.AlterField(
            model_name='licenseactivation',
            name='is_active',
            field=models.BooleanField(default=False, verbose_name='فعال در ربات'),
        ),
    ]
