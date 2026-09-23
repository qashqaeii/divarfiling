from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_workspace', '0002_aiusagelog_provider_attempt_aiusagelog_total_tokens'),
    ]

    operations = [
        migrations.AddField(
            model_name='aiquota',
            name='nl_command_used',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='فرمان هوشمند'),
        ),
    ]
