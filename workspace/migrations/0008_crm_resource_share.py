from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0007_crm_agency_phase4'),
    ]

    operations = [
        migrations.CreateModel(
            name='CRMResourceShare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('note', models.CharField(blank=True, max_length=300, verbose_name='یادداشت')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('agency', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resource_shares', to='workspace.crmagency', verbose_name='آژانس')),
                ('customer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='workspace.customer', verbose_name='مخاطب')),
                ('deal', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='workspace.crmdeal', verbose_name='معامله')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crm_shares_sent', to=settings.AUTH_USER_MODEL, verbose_name='مالک')),
                ('property', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='shares', to='workspace.crmproperty', verbose_name='ملک')),
                ('shared_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crm_shares_created', to=settings.AUTH_USER_MODEL, verbose_name='توسط')),
                ('shared_with', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='crm_shares_received', to=settings.AUTH_USER_MODEL, verbose_name='گیرنده')),
            ],
            options={
                'verbose_name': 'اشتراک CRM',
                'verbose_name_plural': 'اشتراک\u200cهای CRM',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='crmresourceshare',
            constraint=models.UniqueConstraint(condition=models.Q(('customer__isnull', False)), fields=('customer', 'shared_with'), name='uniq_crm_share_customer'),
        ),
        migrations.AddConstraint(
            model_name='crmresourceshare',
            constraint=models.UniqueConstraint(condition=models.Q(('property__isnull', False)), fields=('property', 'shared_with'), name='uniq_crm_share_property'),
        ),
        migrations.AddConstraint(
            model_name='crmresourceshare',
            constraint=models.UniqueConstraint(condition=models.Q(('deal__isnull', False)), fields=('deal', 'shared_with'), name='uniq_crm_share_deal'),
        ),
    ]
