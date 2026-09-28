from django.db import migrations, models


def copy_postal_from_feature_data(apps, schema_editor):
    CRMProperty = apps.get_model('workspace', 'CRMProperty')
    for prop in CRMProperty.objects.iterator():
        if (prop.postal_code or '').strip():
            continue
        fd = prop.feature_data if isinstance(prop.feature_data, dict) else {}
        pc = str(fd.get('کد پستی') or '').strip()
        if not pc:
            continue
        digits = ''.join(c for c in pc if c.isdigit())[:10]
        if digits:
            prop.postal_code = digits
            prop.save(update_fields=['postal_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0068_customer_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='postal_code',
            field=models.CharField(blank=True, max_length=10, verbose_name='کد پستی'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='land_area',
            field=models.FloatField(blank=True, null=True, verbose_name='متراژ زمین'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='frontage_width',
            field=models.FloatField(blank=True, null=True, verbose_name='دهنه ملک'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_wardrobe',
            field=models.BooleanField(default=False, verbose_name='کمد دیواری'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_two_corner',
            field=models.BooleanField(default=False, verbose_name='دو نبش'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_two_access',
            field=models.BooleanField(default=False, verbose_name='دو معبر'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_wallpaper',
            field=models.BooleanField(default=False, verbose_name='کاغذ دیواری'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_knauf',
            field=models.BooleanField(default=False, verbose_name='کناف'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='has_lighting',
            field=models.BooleanField(default=False, verbose_name='نورپردازی'),
        ),
        migrations.RunPython(copy_postal_from_feature_data, migrations.RunPython.noop),
    ]
