# Generated manually for CRM A8/A10

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0004_crm_automation_phase3'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CRMSavedFilter',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, verbose_name='نام')),
                ('scope', models.CharField(
                    choices=[('contacts', 'مخاطبین'), ('properties', 'املاک'), ('deals', 'معاملات')],
                    max_length=20, verbose_name='بخش',
                )),
                ('params', models.JSONField(default=dict, verbose_name='پارامترها')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='سنجاق')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='crm_saved_filters',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='کاربر',
                )),
            ],
            options={
                'verbose_name': 'فیلتر ذخیره CRM',
                'verbose_name_plural': 'فیلترهای ذخیره CRM',
                'ordering': ['-is_pinned', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='crmsavedfilter',
            constraint=models.UniqueConstraint(
                fields=('user', 'scope', 'name'),
                name='uniq_crm_saved_filter_name_scope',
            ),
        ),
    ]
