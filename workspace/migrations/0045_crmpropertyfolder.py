from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0044_customer_lease_deadline'),
    ]

    operations = [
        migrations.CreateModel(
            name='CRMPropertyFolder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80, verbose_name='نام زونکن')),
                ('description', models.CharField(blank=True, max_length=240, verbose_name='توضیح')),
                ('color', models.CharField(default='#6366f1', max_length=7, verbose_name='رنگ')),
                ('icon', models.CharField(default='fa-folder', max_length=40, verbose_name='آیکن')),
                ('sort_order', models.PositiveIntegerField(default=0, verbose_name='ترتیب')),
                ('is_pinned', models.BooleanField(default=False, verbose_name='سنجاق')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crm_property_folders', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'زونکن فایل شخصی',
                'verbose_name_plural': 'زونکن\u200cهای فایل شخصی',
                'ordering': ['-is_pinned', 'sort_order', 'name'],
            },
        ),
        migrations.CreateModel(
            name='CRMPropertyFolderItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added_at', models.DateTimeField(auto_now_add=True)),
                ('folder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='workspace.crmpropertyfolder', verbose_name='زونکن')),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='folder_items', to='workspace.crmproperty', verbose_name='ملک')),
            ],
            options={
                'verbose_name': 'عضو زونکن',
                'verbose_name_plural': 'اعضای زونکن',
                'ordering': ['-added_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='crmpropertyfolder',
            constraint=models.UniqueConstraint(fields=('user', 'name'), name='uniq_crm_property_folder_name'),
        ),
        migrations.AddConstraint(
            model_name='crmpropertyfolderitem',
            constraint=models.UniqueConstraint(fields=('folder', 'property'), name='uniq_crm_folder_property'),
        ),
    ]
