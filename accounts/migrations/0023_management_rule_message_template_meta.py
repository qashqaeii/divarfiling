# Generated manually for Message Template Editor

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('accounts', '0022_merge_management_and_acquisition'),
    ]

    operations = [
        migrations.AddField(
            model_name='managementautomationrule',
            name='message_template_updated_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='به‌روزرسانی قالب پیام'),
        ),
        migrations.AddField(
            model_name='managementautomationrule',
            name='message_template_updated_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='management_automation_message_updates',
                to=settings.AUTH_USER_MODEL,
                verbose_name='ویرایش‌کننده قالب پیام',
            ),
        ),
    ]
