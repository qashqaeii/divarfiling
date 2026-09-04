"""Phase 2 hardening: hashed tokens, acceptance hash, version lock."""
import hashlib

from django.db import migrations, models


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def forwards_hash_tokens(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    for c in Contract.objects.all():
        old = getattr(c, 'verification_token', '') or ''
        if old and not c.verification_token_hash:
            c.verification_token_hash = _hash(old)
            c.save(update_fields=['verification_token_hash'])

    ContractInvitation = apps.get_model('contracts', 'ContractInvitation')
    for inv in ContractInvitation.objects.all():
        old = getattr(inv, 'token', '') or ''
        if old and not inv.token_hash:
            inv.token_hash = _hash(old)
            inv.save(update_fields=['token_hash'])

    ContractAccessToken = apps.get_model('contracts', 'ContractAccessToken')
    for tok in ContractAccessToken.objects.all():
        old = getattr(tok, 'token', '') or ''
        if old and not tok.token_hash:
            tok.token_hash = _hash(old)
            tok.save(update_fields=['token_hash'])

    ContractAcceptance = apps.get_model('contracts', 'ContractAcceptance')
    for acc in ContractAcceptance.objects.all():
        if not acc.accepted_content_hash and acc.content_hash:
            acc.accepted_content_hash = acc.content_hash
            acc.save(update_fields=['accepted_content_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractversion',
            name='is_locked',
            field=models.BooleanField(default=False, verbose_name='قفل‌شده'),
        ),
        migrations.AddField(
            model_name='contract',
            name='verification_token_hash',
            field=models.CharField(
                blank=True, max_length=64, null=True, db_index=True,
                verbose_name='هش توکن تأیید عمومی',
            ),
        ),
        migrations.AddField(
            model_name='contractinvitation',
            name='token_hash',
            field=models.CharField(
                blank=True, max_length=64, null=True, db_index=True, verbose_name='هش توکن',
            ),
        ),
        migrations.AddField(
            model_name='contractinvitation',
            name='resend_count',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='تعداد ارسال مجدد'),
        ),
        migrations.AddField(
            model_name='contractinvitation',
            name='last_sent_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='آخرین ارسال'),
        ),
        migrations.AddField(
            model_name='contractaccesstoken',
            name='token_hash',
            field=models.CharField(
                blank=True, max_length=64, null=True, db_index=True, verbose_name='هش توکن',
            ),
        ),
        migrations.AddField(
            model_name='contractacceptance',
            name='accepted_content_hash',
            field=models.CharField(blank=True, max_length=64, verbose_name='هش محتوای تأییدشده'),
        ),
        migrations.RunPython(forwards_hash_tokens, migrations.RunPython.noop),
        migrations.RemoveIndex(
            model_name='contractinvitation',
            name='contracts_c_token_2d6df9_idx',
        ),
        migrations.RemoveField(model_name='contract', name='verification_token'),
        migrations.RemoveField(model_name='contractinvitation', name='token'),
        migrations.RemoveField(model_name='contractaccesstoken', name='token'),
        migrations.AlterField(
            model_name='contract',
            name='verification_token_hash',
            field=models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن تأیید عمومی'),
        ),
        migrations.AlterField(
            model_name='contractinvitation',
            name='token_hash',
            field=models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن'),
        ),
        migrations.AlterField(
            model_name='contractaccesstoken',
            name='token_hash',
            field=models.CharField(max_length=64, unique=True, db_index=True, verbose_name='هش توکن'),
        ),
        migrations.AlterField(
            model_name='contractacceptance',
            name='accepted_content_hash',
            field=models.CharField(max_length=64, verbose_name='هش محتوای تأییدشده'),
        ),
        migrations.AddIndex(
            model_name='contractinvitation',
            index=models.Index(fields=['token_hash'], name='contracts_c_token_h_6a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='contractinvitation',
            index=models.Index(fields=['contract', 'version'], name='contracts_c_contrac_7d8e9f_idx'),
        ),
        migrations.AddIndex(
            model_name='contractlegalrule',
            index=models.Index(fields=['contract_type', 'status'], name='contracts_c_contrac_1a2b3c_idx'),
        ),
    ]
