from django.db import migrations, models
from django.utils import timezone


def migrate_legacy_property_archive(apps, schema_editor):
    CRMProperty = apps.get_model('workspace', 'CRMProperty')
    now = timezone.now()
    for prop in CRMProperty.objects.filter(transaction_status='بایگانی').iterator():
        if prop.archived_at:
            continue
        prop.archived_at = prop.updated_at or now
        prop.pre_archive_transaction_status = ''
        prop.transaction_status = 'فعال'
        prop.save(update_fields=['archived_at', 'pre_archive_transaction_status', 'transaction_status'])


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0080_customer_property_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان بایگانی'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='archive_reason',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='دلیل بایگانی'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='pre_archive_transaction_status',
            field=models.CharField(blank=True, default='', max_length=30, verbose_name='وضعیت معامله قبل از بایگانی'),
        ),
        migrations.RunPython(migrate_legacy_property_archive, migrations.RunPython.noop),
    ]
