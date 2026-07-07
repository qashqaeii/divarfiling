from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0020_alter_customer_customer_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmproperty',
            name='business_type',
            field=models.CharField(blank=True, max_length=50, verbose_name='نوع آگهی\u200cدهنده'),
        ),
        migrations.AddField(
            model_name='crmproperty',
            name='phone',
            field=models.CharField(blank=True, max_length=20, verbose_name='شماره تماس'),
        ),
    ]
