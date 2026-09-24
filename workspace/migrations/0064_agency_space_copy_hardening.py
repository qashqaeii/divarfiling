# Agency Space copy — target_kind, snapshot, relaxed CHECK for SET_NULL targets

from django.db import migrations, models


def backfill_target_kind(apps, schema_editor):
    AgencySpaceCopy = apps.get_model('workspace', 'AgencySpaceCopy')
    for row in AgencySpaceCopy.objects.all().iterator():
        if row.copied_property_id:
            row.target_kind = 'property'
            row.target_id_snapshot = row.copied_property_id
        elif row.copied_customer_id:
            row.target_kind = 'customer'
            row.target_id_snapshot = row.copied_customer_id
        else:
            row.target_kind = 'property'
        row.save(update_fields=['target_kind', 'target_id_snapshot'])


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0063_agency_space_copy'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='agencyspacecopy',
            name='agency_space_copy_one_target',
        ),
        migrations.AddField(
            model_name='agencyspacecopy',
            name='target_kind',
            field=models.CharField(
                choices=[('property', 'ملک'), ('customer', 'مخاطب')],
                default='property',
                max_length=12,
                verbose_name='نوع نسخه شخصی',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='agencyspacecopy',
            name='target_id_snapshot',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                help_text='پس از حذف نسخه شخصی برای provenance و شمارش تاریخی',
                verbose_name='شناسه نسخه شخصی (تاریخی)',
            ),
        ),
        migrations.RunPython(backfill_target_kind, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='agencyspacecopy',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('target_kind', 'property'), ('copied_customer__isnull', True),
                ) | models.Q(
                    ('target_kind', 'customer'), ('copied_property__isnull', True),
                ),
                name='agency_space_copy_kind_shape',
            ),
        ),
    ]
