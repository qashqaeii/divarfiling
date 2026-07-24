from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0004_longer_slugs_for_market_articles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='marketarticlerun',
            name='status',
            field=models.CharField(
                choices=[
                    ('building', 'در حال ساخت'),
                    ('preview', 'پیش‌نمایش'),
                    ('draft_linked', 'متصل به پیش‌نویس'),
                    ('failed', 'ناموفق'),
                    ('discarded', 'لغو شده'),
                ],
                db_index=True,
                default='preview',
                max_length=20,
                verbose_name='وضعیت',
            ),
        ),
    ]
