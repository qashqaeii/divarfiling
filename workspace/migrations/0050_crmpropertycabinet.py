# Generated manually for Property Cabinets

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0049_dataset_updated_at_index'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CRMPropertyCabinet',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='نام کمد')),
                ('description', models.CharField(blank=True, max_length=240, verbose_name='توضیح')),
                ('color', models.CharField(default='#6366f1', max_length=7, verbose_name='رنگ')),
                ('icon', models.CharField(default='fa-folder', max_length=40, verbose_name='آیکن')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='ترتیب')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='سنجاق')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crm_property_cabinets', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'کمد فایل شخصی',
                'verbose_name_plural': 'کمدهای فایل شخصی',
                'ordering': ['-is_pinned', 'sort_order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='crmpropertycabinet',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='uniq_crm_property_cabinet_name'),
        ),
        migrations.AddField(
            model_name='crmpropertyfolder',
            name='cabinet',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='folders', to='workspace.crmpropertycabinet', verbose_name='کمد'),
        ),
    ]
