from django.conf import settings
from django.db import migrations, models


def dedupe_user_discount_issuances(apps, schema_editor):
    """یک ردیف به ازای هر (user, policy_key) — جدیدترین صدور حفظ می‌شود."""
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM accounts_userdiscountissuance u
                WHERE u.id NOT IN (
                    SELECT DISTINCT ON (user_id, policy_key) id
                    FROM accounts_userdiscountissuance
                    ORDER BY user_id, policy_key, issued_at DESC, id DESC
                )
                """
            )
        return

    UserDiscountIssuance = apps.get_model('accounts', 'UserDiscountIssuance')
    seen = {}
    to_delete = []
    for row in (
        UserDiscountIssuance.objects.all()
        .order_by('user_id', 'policy_key', '-issued_at', '-id')
        .values_list('id', 'user_id', 'policy_key')
    ):
        row_id, user_id, policy_key = row
        key = (user_id, policy_key)
        if key in seen:
            to_delete.append(row_id)
        else:
            seen[key] = row_id
    if to_delete:
        UserDiscountIssuance.objects.filter(pk__in=to_delete).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0029_smsmessagelog_message_preview'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(dedupe_user_discount_issuances, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='userdiscountissuance',
            constraint=models.UniqueConstraint(
                fields=('user', 'policy_key'),
                name='uniq_user_discount_policy',
            ),
        ),
    ]
