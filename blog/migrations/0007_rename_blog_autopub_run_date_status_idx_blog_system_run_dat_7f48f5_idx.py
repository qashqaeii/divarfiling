# Index rename — already applied on some production servers (keep name in sync).

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0006_systematic_article_autopublish'),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='systematicarticleautopublishrun',
            new_name='blog_system_run_dat_7f48f5_idx',
            old_name='blog_autopub_run_date_status_idx',
        ),
    ]
