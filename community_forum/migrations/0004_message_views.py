from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('community_forum', '0003_forummessage_pinned'),
    ]

    operations = [
        migrations.AddField(
            model_name='forummessage',
            name='view_count',
            field=models.PositiveIntegerField(default=0, verbose_name='تعداد بازدید'),
        ),
        migrations.CreateModel(
            name='ForumMessageView',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='message_views', to='community_forum.forummember', verbose_name='عضو')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='viewer_rows', to='community_forum.forummessage', verbose_name='پیام')),
            ],
            options={
                'verbose_name': 'بازدید پیام',
                'verbose_name_plural': 'بازدیدهای پیام',
            },
        ),
        migrations.AddConstraint(
            model_name='forummessageview',
            constraint=models.UniqueConstraint(fields=('message', 'member'), name='uniq_forum_msg_view'),
        ),
        migrations.AddIndex(
            model_name='forummessageview',
            index=models.Index(fields=['message'], name='community_f_message_6a8f2d_idx'),
        ),
    ]
