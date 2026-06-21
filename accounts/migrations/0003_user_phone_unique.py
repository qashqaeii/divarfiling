"""Data migration: normalize and uniquify phone numbers."""
import re

from django.db import migrations, models

PERSIAN_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')


def _normalize_phone(raw: str) -> str:
    if not raw:
        return ''
    s = str(raw).strip().translate(PERSIAN_DIGITS)
    s = re.sub(r'[\s\-()]+', '', s)
    if s.startswith('+98'):
        s = '0' + s[3:]
    elif s.startswith('0098'):
        s = '0' + s[4:]
    elif s.startswith('98') and len(s) == 12:
        s = '0' + s[2:]
    elif s.startswith('9') and len(s) == 10:
        s = '0' + s
    return s


def prepare_unique_phones(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    seen = set()
    for user in User.objects.order_by('pk'):
        phone = _normalize_phone(user.phone)
        if not phone or not re.fullmatch(r'09\d{9}', phone):
            phone = f'0990000{user.pk:04d}'
        base = phone
        n = 0
        while phone in seen:
            n += 1
            phone = f'{base[:9]}{n:02d}'[-11:]
            if not phone.startswith('09'):
                phone = f'0990000{user.pk:04d}'
                if phone in seen:
                    phone = f'0999{user.pk:06d}'[:11]
        seen.add(phone)
        if user.phone != phone:
            user.phone = phone
            user.save(update_fields=['phone'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_referred_by'),
    ]

    operations = [
        migrations.RunPython(prepare_unique_phones, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='user',
            name='phone',
            field=models.CharField(max_length=20, unique=True, verbose_name='شماره موبایل'),
        ),
    ]
