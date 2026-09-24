# Generated manually — Agency Space Phase 1

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0061_propertyaccessibilityjob'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AgencySpaceItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('visibility', models.CharField(
                    choices=[('agency_public', 'عمومی آژانس'), ('selected_members', 'اعضای منتخب')],
                    default='agency_public', max_length=24, verbose_name='دسترسی',
                )),
                ('status', models.CharField(
                    choices=[
                        ('active', 'فعال'),
                        ('archived', 'بایگانی'),
                        ('moderation_hidden', 'مخفی‌شده توسط مدیریت'),
                    ],
                    db_index=True, default='active', max_length=20, verbose_name='وضعیت',
                )),
                ('contact_share_level', models.CharField(
                    blank=True,
                    choices=[('summary', 'خلاصه بدون تماس'), ('full', 'شامل اطلاعات تماس')],
                    default='summary', max_length=12, verbose_name='سطح اشتراک مخاطب',
                )),
                ('note', models.CharField(blank=True, max_length=300, verbose_name='یادداشت')),
                ('published_at', models.DateTimeField(auto_now_add=True, verbose_name='زمان انتشار')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('archived_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان بایگانی')),
                ('archived_reason', models.CharField(
                    blank=True, choices=[
                        ('user_unpublish', 'لغو انتشار'),
                        ('member_left', 'خروج عضو'),
                        ('member_deactivated', 'غیرفعال شدن عضو'),
                        ('source_deleted', 'حذف منبع'),
                        ('moderation', 'مدیریت'),
                    ],
                    default='', max_length=24, verbose_name='دلیل بایگانی',
                )),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='space_items', to='workspace.crmagency', verbose_name='آژانس',
                )),
                ('customer', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='agency_space_items', to='workspace.customer', verbose_name='مخاطب',
                )),
                ('property', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='agency_space_items', to='workspace.crmproperty', verbose_name='ملک',
                )),
                ('publisher', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='agency_space_publications', to=settings.AUTH_USER_MODEL,
                    verbose_name='ناشر',
                )),
            ],
            options={
                'verbose_name': 'آیتم فضای آژانس',
                'verbose_name_plural': 'آیتم‌های فضای آژانس',
                'ordering': ['-published_at'],
            },
        ),
        migrations.CreateModel(
            name='AgencySpaceItemMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='audience_members', to='workspace.agencyspaceitem', verbose_name='آیتم',
                )),
                ('member', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='space_audience_items', to='workspace.crmagencymember',
                    verbose_name='عضو',
                )),
            ],
            options={
                'verbose_name': 'مخاطب audience فضای آژانس',
                'verbose_name_plural': 'مخاطبان audience فضای آژانس',
            },
        ),
        migrations.AddConstraint(
            model_name='agencyspaceitem',
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(('customer__isnull', True), ('property__isnull', False)),
                    models.Q(('customer__isnull', False), ('property__isnull', True)),
                    _connector='OR',
                ),
                name='agency_space_item_one_source',
            ),
        ),
        migrations.AddConstraint(
            model_name='agencyspaceitem',
            constraint=models.UniqueConstraint(
                condition=models.Q(('property__isnull', False), ('status', 'active')),
                fields=('agency', 'publisher', 'property'),
                name='uniq_active_space_property_pub',
            ),
        ),
        migrations.AddConstraint(
            model_name='agencyspaceitem',
            constraint=models.UniqueConstraint(
                condition=models.Q(('customer__isnull', False), ('status', 'active')),
                fields=('agency', 'publisher', 'customer'),
                name='uniq_active_space_customer_pub',
            ),
        ),
        migrations.AddConstraint(
            model_name='agencyspaceitemmember',
            constraint=models.UniqueConstraint(
                fields=('item', 'member'), name='uniq_agency_space_item_member',
            ),
        ),
        migrations.AddIndex(
            model_name='agencyspaceitem',
            index=models.Index(fields=['agency', 'status', '-published_at'], name='workspace_a_agency__a8f4e2_idx'),
        ),
        migrations.AddIndex(
            model_name='agencyspaceitem',
            index=models.Index(fields=['agency', 'publisher', 'status'], name='workspace_a_agency__b2c1d0_idx'),
        ),
    ]
