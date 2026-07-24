# Generated manually for market article long slugs

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0003_market_article_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(max_length=120, unique=True, verbose_name='نامک'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='name',
            field=models.CharField(max_length=100, unique=True, verbose_name='نام'),
        ),
        migrations.AlterField(
            model_name='tag',
            name='slug',
            field=models.SlugField(max_length=120, unique=True, verbose_name='نامک'),
        ),
        migrations.AlterField(
            model_name='post',
            name='slug',
            field=models.SlugField(max_length=220, unique=True, verbose_name='نامک'),
        ),
    ]
