from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0019_customer_builder_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='customer_type',
            field=models.CharField(
                choices=[
                    ('خریدار', 'خریدار'),
                    ('فروشنده', 'فروشنده'),
                    ('سازنده', 'سازنده'),
                    ('مالک', 'مالک'),
                    ('مستاجر', 'مستاجر'),
                    ('موجر', 'موجر'),
                    ('سرمایه\u200cگذار', 'سرمایه\u200cگذار'),
                    ('سرنخ', 'سرنخ'),
                    ('متقاضی خرید', 'متقاضی خرید'),
                    ('متقاضی اجاره', 'متقاضی اجاره'),
                    ('فروشنده ملک', 'فروشنده ملک'),
                    ('اشخاص حقوقی', 'اشخاص حقوقی'),
                ],
                default='خریدار',
                max_length=30,
                verbose_name='نوع مخاطب',
            ),
        ),
        migrations.AlterField(
            model_name='customerlisting',
            name='role',
            field=models.CharField(
                choices=[
                    ('مالک', 'مالک'),
                    ('فروشنده', 'فروشنده'),
                    ('خریدار', 'خریدار'),
                    ('سازنده', 'سازنده'),
                    ('مستاجر', 'مستاجر'),
                    ('موجر', 'موجر'),
                    ('سرمایه\u200cگذار', 'سرمایه\u200cگذار'),
                    ('سرنخ', 'سرنخ'),
                    ('پیشنهادی', 'پیشنهادی'),
                    ('متقاضی خرید', 'متقاضی خرید'),
                    ('متقاضی اجاره', 'متقاضی اجاره'),
                ],
                default='پیشنهادی',
                max_length=30,
                verbose_name='نقش',
            ),
        ),
        migrations.AlterField(
            model_name='propertycontact',
            name='role',
            field=models.CharField(
                choices=[
                    ('مالک', 'مالک'),
                    ('فروشنده', 'فروشنده'),
                    ('خریدار', 'خریدار'),
                    ('سازنده', 'سازنده'),
                    ('مستاجر', 'مستاجر'),
                    ('موجر', 'موجر'),
                    ('سرمایه\u200cگذار', 'سرمایه\u200cگذار'),
                    ('سرنخ', 'سرنخ'),
                    ('پیشنهادی', 'پیشنهادی'),
                    ('متقاضی خرید', 'متقاضی خرید'),
                    ('متقاضی اجاره', 'متقاضی اجاره'),
                ],
                default='پیشنهادی',
                max_length=30,
                verbose_name='نقش',
            ),
        ),
    ]
