"""سه‌برابر کردن سقف روزانهٔ ذخیره‌شده برای کاربران (غیر unlimited)."""
from django.db import migrations
from django.db.models import F


def scale_daily_limits(apps, schema_editor):
    AIQuota = apps.get_model('ai_workspace', 'AIQuota')
    AIQuota.objects.filter(is_unlimited=False, daily_limit__gt=0).update(
        daily_limit=F('daily_limit') * 3,
    )


def reverse_scale(apps, schema_editor):
    AIQuota = apps.get_model('ai_workspace', 'AIQuota')
    AIQuota.objects.filter(is_unlimited=False, daily_limit__gt=0).update(
        daily_limit=F('daily_limit') / 3,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('ai_workspace', '0003_aiquota_nl_command_used'),
    ]

    operations = [
        migrations.RunPython(scale_daily_limits, reverse_scale),
    ]
