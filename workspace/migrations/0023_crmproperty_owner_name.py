from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0022_support_tickets'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='owner_name',
            field=models.CharField(blank=True, max_length=200, verbose_name='نام مالک'),
        ),
    ]
