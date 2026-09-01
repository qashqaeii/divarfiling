"""Source identity for CRMProperty — prevent duplicate Divar filing imports."""

from django.db import migrations, models


def backfill_divar_source(apps, schema_editor):
    CRMProperty = apps.get_model('workspace', 'CRMProperty')
    qs = CRMProperty.objects.filter(
        token__gt='',
        source_external_id='',
    ).order_by('user_id', 'token', 'pk')
    seen = set()
    for prop in qs.iterator():
        key = (prop.user_id, prop.token)
        if key in seen:
            continue
        seen.add(key)
        CRMProperty.objects.filter(pk=prop.pk).update(
            source_platform='divar',
            source_external_id=prop.token,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0050_crmpropertycabinet'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='source_platform',
            field=models.CharField(
                blank=True, db_index=True, max_length=30, verbose_name='پلتفرم منبع',
            ),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='source_external_id',
            field=models.CharField(
                blank=True, db_index=True, max_length=100, verbose_name='شناسه آگهی منبع',
            ),
        ),
        migrations.RunPython(backfill_divar_source, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='crmproperty',
            constraint=models.UniqueConstraint(
                condition=models.Q(source_external_id__gt=''),
                fields=('user', 'source_platform', 'source_external_id'),
                name='uniq_crmproperty_user_source_listing',
            ),
        ),
    ]
