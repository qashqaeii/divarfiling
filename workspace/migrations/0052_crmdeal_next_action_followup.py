from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('workspace', '0051_crmproperty_source_identity'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmdeal',
            name='next_action_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='زمان اقدام بعدی'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='next_action_note',
            field=models.CharField(blank=True, max_length=300, verbose_name='یادداشت اقدام بعدی'),
        ),
        migrations.AddField(
            model_name='crmdeal',
            name='next_action_type',
            field=models.CharField(blank=True, max_length=30, verbose_name='نوع اقدام بعدی'),
        ),
        migrations.CreateModel(
            name='CRMDealFollowUp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('follow_up_type', models.CharField(max_length=30, verbose_name='نوع پیگیری')),
                ('note', models.TextField(blank=True, verbose_name='نتیجه')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('deal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to='workspace.crmdeal', verbose_name='معامله')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deal_follow_ups', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'پیگیری معامله',
                'verbose_name_plural': 'پیگیری\u200cهای معامله',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['deal', '-created_at'], name='workspace_c_deal_id_6a8f2d_idx')],
            },
        ),
        migrations.AddIndex(
            model_name='crmdeal',
            index=models.Index(fields=['user', 'next_action_at'], name='workspace_c_user_id_9c4e1a_idx'),
        ),
    ]
