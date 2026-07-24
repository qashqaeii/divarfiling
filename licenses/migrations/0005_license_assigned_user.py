# Generated manually for agency license assignment

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('licenses', '0004_license_bulk_order_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='license',
            name='assigned_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='تاریخ تخصیص کلید'),
        ),
        migrations.AddField(
            model_name='license',
            name='assigned_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='licenses_assigned_by_me',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تخصیص توسط',
            ),
        ),
        migrations.AddField(
            model_name='license',
            name='assigned_user',
            field=models.ForeignKey(
                blank=True,
                help_text='عضو تیم که این کلید لایسنس به او اختصاص داده شده است.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='allocated_licenses',
                to=settings.AUTH_USER_MODEL,
                verbose_name='تخصیص به عضو',
            ),
        ),
    ]
