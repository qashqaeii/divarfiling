# CRM Phase 4 — Agency team

import secrets

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _gen_key():
    return secrets.token_hex(24)


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0006_crm_deal_stages_checklist'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CRMAgency',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, verbose_name='نام آژانس')),
                ('slug', models.SlugField(blank=True, max_length=80, unique=True, verbose_name='شناسه')),
                ('api_key', models.CharField(blank=True, max_length=64, unique=True, verbose_name='کلید API')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='owned_crm_agencies',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='مالک',
                )),
            ],
            options={
                'verbose_name': 'آژانس CRM',
                'verbose_name_plural': 'آژانس‌های CRM',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CRMAgencyMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[
                        ('owner', 'مالک'), ('manager', 'مدیر'),
                        ('advisor', 'مشاور'), ('secretary', 'منشی'),
                    ],
                    default='advisor', max_length=20, verbose_name='نقش',
                )),
                ('title', models.CharField(blank=True, max_length=100, verbose_name='عنوان شغلی')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='workspace.crmagency',
                    verbose_name='آژانس',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_agency_memberships',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'عضو آژانس',
                'verbose_name_plural': 'اعضای آژانس',
                'ordering': ['role', 'joined_at'],
            },
        ),
        migrations.CreateModel(
            name='CRMAgencyWebhook',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='نام')),
                ('url', models.URLField(max_length=500, verbose_name='آدرس')),
                ('secret', models.CharField(blank=True, max_length=64, verbose_name='رمز امضا')),
                ('events', models.JSONField(blank=True, default=list, verbose_name='رویدادها')),
                ('is_active', models.BooleanField(default=True, verbose_name='فعال')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='webhooks',
                    to='workspace.crmagency',
                    verbose_name='آژانس',
                )),
            ],
            options={
                'verbose_name': 'وب‌هوک آژانس',
                'verbose_name_plural': 'وب‌هوک‌های آژانس',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CustomerTransferLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(blank=True, max_length=300, verbose_name='یادداشت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfer_logs',
                    to='workspace.crmagency',
                    verbose_name='آژانس',
                )),
                ('customer', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='transfer_logs',
                    to='workspace.customer',
                    verbose_name='مخاطب',
                )),
                ('from_user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='از',
                )),
                ('to_user', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='به',
                )),
                ('transferred_by', models.ForeignKey(
                    null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='توسط',
                )),
            ],
            options={
                'verbose_name': 'انتقال پرونده',
                'verbose_name_plural': 'انتقالات پرونده',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CRMDealCommissionSplit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('percent', models.FloatField(default=0, verbose_name='درصد')),
                ('amount', models.BigIntegerField(blank=True, null=True, verbose_name='مبلغ')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commission_splits',
                    to='workspace.crmdeal',
                    verbose_name='معامله',
                )),
                ('member', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='commission_splits',
                    to='workspace.crmagencymember',
                    verbose_name='عضو',
                )),
            ],
            options={
                'verbose_name': 'سهم کمیسیون',
                'verbose_name_plural': 'سهم‌های کمیسیون',
            },
        ),
        migrations.AddField(
            model_name='customer',
            name='agency',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='customers', to='workspace.crmagency', verbose_name='آژانس',
            ),
        ),
        migrations.AddField(
            model_name='customer',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_assigned_customers', to=settings.AUTH_USER_MODEL,
                verbose_name='مشاور مسئول',
            ),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='agency',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='properties', to='workspace.crmagency', verbose_name='آژانس',
            ),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='agency',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='deals', to='workspace.crmagency', verbose_name='آژانس',
            ),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='assigned_to',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='crm_assigned_deals', to=settings.AUTH_USER_MODEL,
                verbose_name='مشاور مسئول',
            ),
        ),
        migrations.AddIndex(
            model_name='customer',
            index=models.Index(fields=['agency', 'assigned_to'], name='workspace_cu_agency__a8f3c2_idx'),
        ),
        migrations.AddConstraint(
            model_name='crmagencymember',
            constraint=models.UniqueConstraint(fields=('agency', 'user'), name='uniq_agency_member'),
        ),
        migrations.AddConstraint(
            model_name='crmdealcommissionsplit',
            constraint=models.UniqueConstraint(fields=('deal', 'member'), name='uniq_deal_commission_member'),
        ),
    ]
