from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community_forum', '0001_initial_forum'),
    ]

    operations = [
        migrations.AddField(
            model_name='forummessage',
            name='reactions_updated_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
