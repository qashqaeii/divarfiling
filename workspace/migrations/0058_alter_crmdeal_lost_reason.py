# CRM deal lost_reason choices — parallel branch before agency 0058 merge

from django.db import migrations, models

_LOST_REASON_CHOICES = [
    ('قیمت', 'قیمت'),
    ('عدم توافق مالک', 'عدم توافق مالک'),
    ('عدم توافق مشتری', 'عدم توافق مشتری'),
    ('ملک نامناسب', 'ملک نامناسب'),
    ('رقیب', 'رقیب'),
    ('عدم پاسخ', 'عدم پاسخ'),
    ('زمان‌بندی', 'زمان‌بندی'),
    ('سایر', 'سایر'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0056_advertiser_signal_feedback'),
    ]

    operations = [
        migrations.AlterField(
            model_name='crmdeal',
            name='lost_reason',
            field=models.CharField(
                blank=True,
                choices=_LOST_REASON_CHOICES,
                max_length=50,
                verbose_name='دلیل از دست دادن',
            ),
        ),
    ]
