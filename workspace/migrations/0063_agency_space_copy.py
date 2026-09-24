# Agency Space Phase 2 — AgencySpaceCopy

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0062_agency_space_phase1'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgencySpaceCopy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان کپی')),
                ('copied_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='agency_space_copies', to=settings.AUTH_USER_MODEL,
                    verbose_name='کپی‌کننده',
                )),
                ('copied_customer', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='agency_space_copy_origin', to='workspace.customer',
                    verbose_name='مخاطب کپی‌شده',
                )),
                ('copied_property', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='agency_space_copy_origin', to='workspace.crmproperty',
                    verbose_name='ملک کپی‌شده',
                )),
                ('item', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='space_copies', to='workspace.agencyspaceitem',
                    verbose_name='آیتم فضا',
                )),
            ],
            options={
                'verbose_name': 'کپی فضای آژانس',
                'verbose_name_plural': 'کپی‌های فضای آژانس',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='agencyspacecopy',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('copied_property__isnull', False), ('copied_customer__isnull', True),
                ) | models.Q(
                    ('copied_property__isnull', True), ('copied_customer__isnull', False),
                ),
                name='agency_space_copy_one_target',
            ),
        ),
        migrations.AddConstraint(
            model_name='agencyspacecopy',
            constraint=models.UniqueConstraint(
                fields=('item', 'copied_by'),
                name='uniq_agency_space_copy_per_user',
            ),
        ),
        migrations.AddIndex(
            model_name='agencyspacecopy',
            index=models.Index(fields=['item', 'copied_by'], name='workspace_ag_item_id_copied_idx'),
        ),
        migrations.AddIndex(
            model_name='agencyspacecopy',
            index=models.Index(fields=['copied_by', '-created_at'], name='workspace_ag_copied_by_idx'),
        ),
    ]
