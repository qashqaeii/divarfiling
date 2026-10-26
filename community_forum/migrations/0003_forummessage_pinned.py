from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('community_forum', '0002_forummessage_reactions_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='forummessage',
            name='pinned_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='زمان سنجاق'),
        ),
        migrations.AddField(
            model_name='forummessage',
            name='pinned_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='forum_messages_pinned',
                to=settings.AUTH_USER_MODEL,
                verbose_name='سنجاق‌کننده',
            ),
        ),
    ]
