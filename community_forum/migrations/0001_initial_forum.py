import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ForumMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('display_name', models.CharField(blank=True, max_length=64, verbose_name='نام نمایشی')),
                ('display_name_approved', models.BooleanField(default=False, verbose_name='نام نمایشی تأیید‌شده')),
                ('last_read_message_id', models.BigIntegerField(blank=True, null=True, verbose_name='آخرین پیام خوانده‌شده')),
                ('welcome_seen_at', models.DateTimeField(blank=True, null=True, verbose_name='خوش‌آمد دیده شده')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='forum_member', to=settings.AUTH_USER_MODEL, verbose_name='کاربر')),
            ],
            options={
                'verbose_name': 'عضو تالار',
                'verbose_name_plural': 'اعضای تالار',
            },
        ),
        migrations.CreateModel(
            name='ForumMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='متن')),
                ('client_message_id', models.UUIDField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('edited_at', models.DateTimeField(blank=True, null=True)),
                ('deleted_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('reply_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='community_forum.forummessage', verbose_name='پاسخ به')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='community_forum.forummember', verbose_name='فرستنده')),
            ],
            options={
                'verbose_name': 'پیام تالار',
                'verbose_name_plural': 'پیام‌های تالار',
                'permissions': [('can_moderate_forum', 'مدیریت تالار گفتگو')],
            },
        ),
        migrations.CreateModel(
            name='ForumPinnedNotice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('body', models.TextField(verbose_name='متن اطلاعیه')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forum_notices_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'اطلاعیه سنجاق‌شده',
                'verbose_name_plural': 'اطلاعیه‌های سنجاق‌شده',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ForumModerationAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(db_index=True, max_length=64)),
                ('target_message_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('target_member_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('meta', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forum_audit_actions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'سابقه مدیریت تالار',
                'verbose_name_plural': 'سوابق مدیریت تالار',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ForumBan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(blank=True)),
                ('can_read', models.BooleanField(default=True, verbose_name='اجازه مشاهده')),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                ('revoked_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forum_bans_created', to=settings.AUTH_USER_MODEL)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bans', to='community_forum.forummember')),
            ],
            options={
                'verbose_name': 'محدودیت تالار',
                'verbose_name_plural': 'محدودیت‌های تالار',
            },
        ),
        migrations.CreateModel(
            name='ForumReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(max_length=32)),
                ('note', models.CharField(blank=True, max_length=500)),
                ('status', models.CharField(choices=[('pending', 'در انتظار'), ('reviewed', 'بررسی‌شده'), ('dismissed', 'رد شده')], db_index=True, default='pending', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='community_forum.forummessage')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports_filed', to='community_forum.forummember')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='forum_reports_reviewed', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'گزارش تخلف',
                'verbose_name_plural': 'گزارش‌های تخلف',
            },
        ),
        migrations.CreateModel(
            name='ForumReaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('emoji', models.CharField(max_length=8)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='community_forum.forummember')),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reactions', to='community_forum.forummessage')),
            ],
            options={
                'verbose_name': 'واکنش',
                'verbose_name_plural': 'واکنش‌ها',
            },
        ),
        migrations.AddIndex(
            model_name='forummessage',
            index=models.Index(fields=['-created_at', '-id'], name='community_f_created_6e0f0d_idx'),
        ),
        migrations.AddIndex(
            model_name='forummessage',
            index=models.Index(fields=['sender', 'client_message_id'], name='community_f_sender__f8a2c1_idx'),
        ),
        migrations.AddConstraint(
            model_name='forummessage',
            constraint=models.UniqueConstraint(condition=models.Q(('client_message_id__isnull', False)), fields=('sender', 'client_message_id'), name='uniq_forum_client_message_per_sender'),
        ),
        migrations.AddConstraint(
            model_name='forumreaction',
            constraint=models.UniqueConstraint(fields=('message', 'member'), name='uniq_forum_reaction_per_member'),
        ),
        migrations.AddConstraint(
            model_name='forumreport',
            constraint=models.UniqueConstraint(fields=('message', 'reporter'), name='uniq_forum_report_per_reporter'),
        ),
        migrations.AddIndex(
            model_name='forumban',
            index=models.Index(fields=['member', '-starts_at'], name='community_f_member__a1b2c3_idx'),
        ),
    ]
