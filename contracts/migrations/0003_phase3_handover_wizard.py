"""Phase 3: handover, party share, witness role, attachment handover FK."""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0002_phase2_hardening'),
        ('workspace', '0056_advertiser_signal_feedback'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='contractparty',
            name='ownership_share',
            field=models.CharField(blank=True, max_length=40, verbose_name='قدرالسهم'),
        ),
        migrations.AddField(
            model_name='contractwitness',
            name='witness_role',
            field=models.CharField(blank=True, max_length=30, verbose_name='نقش شاهد'),
        ),
        migrations.CreateModel(
            name='ContractHandover',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('handover_type', models.CharField(
                    choices=[('initial_delivery', 'تحویل اولیه')],
                    default='initial_delivery', max_length=30, verbose_name='نوع تحویل',
                )),
                ('status', models.CharField(
                    choices=[('draft', 'پیش\u200cنویس'), ('sent', 'ارسال\u200cشده'), ('finalized', 'تأییدشده')],
                    db_index=True, default='draft', max_length=20, verbose_name='وضعیت',
                )),
                ('handover_date', models.DateField(blank=True, null=True, verbose_name='تاریخ تحویل')),
                ('handover_time', models.TimeField(blank=True, null=True, verbose_name='ساعت تحویل')),
                ('snapshot_json', models.JSONField(blank=True, default=dict, verbose_name='اسنپ\u200cشات')),
                ('content_hash', models.CharField(blank=True, max_length=64, verbose_name='هش محتوا')),
                ('notes', models.TextField(blank=True, verbose_name='یادداشت')),
                ('pdf_file', models.FileField(blank=True, upload_to='contracts/handovers/', verbose_name='PDF')),
                ('is_locked', models.BooleanField(default=False, verbose_name='قفل\u200cشده')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('finalized_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان نهایی\u200cسازی')),
                ('contract', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='handovers', to='contracts.contract', verbose_name='قرارداد',
                )),
                ('deal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contract_handovers', to='workspace.crmdeal', verbose_name='معامله',
                )),
                ('replaced_by', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='replaces', to='contracts.contracthandover', verbose_name='جایگزین\u200cشده با',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='contract_handovers', to=settings.AUTH_USER_MODEL, verbose_name='ایجادکننده',
                )),
                ('version', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='handovers', to='contracts.contractversion', verbose_name='نسخه قرارداد',
                )),
            ],
            options={
                'verbose_name': 'صورت\u200cجلسه تحویل',
                'verbose_name_plural': 'صورت\u200cجلسه\u200cهای تحویل',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterField(
            model_name='contractattachment',
            name='version',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='attachments', to='contracts.contractversion', verbose_name='نسخه',
            ),
        ),
        migrations.AddField(
            model_name='contractattachment',
            name='handover',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='attachments', to='contracts.contracthandover',
                verbose_name='صورت\u200cجلسه تحویل',
            ),
        ),
        migrations.CreateModel(
            name='ContractHandoverInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('side', models.CharField(max_length=20, verbose_name='سمت')),
                ('first_name', models.CharField(blank=True, max_length=100, verbose_name='نام')),
                ('last_name', models.CharField(blank=True, max_length=100, verbose_name='نام خانوادگی')),
                ('national_id', models.CharField(blank=True, max_length=10, verbose_name='کد ملی')),
                ('mobile', models.CharField(max_length=20, verbose_name='موبایل')),
                ('token_hash', models.CharField(db_index=True, max_length=64, unique=True, verbose_name='هش توکن')),
                ('expires_at', models.DateTimeField(verbose_name='انقضا')),
                ('is_revoked', models.BooleanField(default=False, verbose_name='ابطال\u200cشده')),
                ('sms_status', models.CharField(default='queued', max_length=20, verbose_name='وضعیت SMS')),
                ('sms_sent_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان ارسال SMS')),
                ('last_sent_at', models.DateTimeField(blank=True, null=True, verbose_name='آخرین ارسال')),
                ('resend_count', models.PositiveSmallIntegerField(default=0, verbose_name='تعداد ارسال مجدد')),
                ('opened_at', models.DateTimeField(blank=True, null=True, verbose_name='زمان باز شدن')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('handover', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invitations', to='contracts.contracthandover', verbose_name='صورت\u200cجلسه',
                )),
            ],
            options={
                'verbose_name': 'دعوتنامه تحویل',
                'verbose_name_plural': 'دعوتنامه\u200cهای تحویل',
            },
        ),
        migrations.CreateModel(
            name='ContractHandoverAcceptance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('side', models.CharField(max_length=20, verbose_name='سمت')),
                ('accepted_content_hash', models.CharField(max_length=64, verbose_name='هش تأییدشده')),
                ('mobile', models.CharField(max_length=20, verbose_name='موبایل')),
                ('national_id_entered', models.CharField(blank=True, max_length=10, verbose_name='کد ملی')),
                ('otp_verified_at', models.DateTimeField(verbose_name='زمان OTP')),
                ('ack_checkboxes', models.JSONField(blank=True, default=list, verbose_name='تأییدها')),
                ('accepted_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='زمان تأیید')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP')),
                ('handover', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='acceptances', to='contracts.contracthandover', verbose_name='صورت\u200cجلسه',
                )),
                ('invitation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='acceptances', to='contracts.contracthandoverinvitation',
                    verbose_name='دعوتنامه',
                )),
            ],
            options={
                'verbose_name': 'تأیید تحویل',
                'verbose_name_plural': 'تأییدهای تحویل',
            },
        ),
        migrations.AddConstraint(
            model_name='contracthandoveracceptance',
            constraint=models.UniqueConstraint(
                fields=('handover', 'side'), name='contracts_handover_side_uniq',
            ),
        ),
        migrations.AlterField(
            model_name='contractotp',
            name='invitation',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='otp_requests', to='contracts.contractinvitation', verbose_name='دعوتنامه',
            ),
        ),
        migrations.AddField(
            model_name='contractotp',
            name='handover_invitation',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='otp_requests', to='contracts.contracthandoverinvitation',
                verbose_name='دعوتنامه تحویل',
            ),
        ),
    ]
