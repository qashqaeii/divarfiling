from django.db import migrations, models


def migrate_legacy_contact_archive(apps, schema_editor):
    Customer = apps.get_model('workspace', 'Customer')
    for customer in Customer.objects.filter(status='بایگانی').iterator():
        if customer.archived_at:
            continue
        customer.archived_at = customer.updated_at
        customer.save(update_fields=['archived_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0082_property_rental_renewal'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان بایگانی'),
        ),
        migrations.AddField(
            model_name='customer',
            name='archive_reason',
            field=models.CharField(blank=True, default='', max_length=500, verbose_name='دلیل بایگانی'),
        ),
        migrations.RunPython(migrate_legacy_contact_archive, migrations.RunPython.noop),
    ]
