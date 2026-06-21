"""
دستور مدیریتی برای وارد کردن محصول نسخه پایه V1.0
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from shop.models import Product, ProductMedia, LicensePlan


class Command(BaseCommand):
    help = 'وارد کردن محصول نسخه پایه V1.0 ربات دیوار'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('شروع وارد کردن محصول نسخه پایه...'))
        
        # ایجاد محصول نسخه پایه
        product, created = Product.objects.get_or_create(
            slug='basic-v1',
            defaults={
                'title': 'ربات هوشمند تحلیل املاک دیوار - نسخه پایه V1.0',
                'description': self.get_product_description(),
                'short_description': 'ابزار ساده و کاربردی برای استخراج و جمع‌آوری داده‌های املاک از وب‌سایت دیوار در فایل اکسل',
                'features': self.get_product_features(),
                'is_active': True,
                'order': 2,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'محصول "{product.title}" ایجاد شد.'))
        else:
            self.stdout.write(self.style.WARNING(f'محصول "{product.title}" از قبل وجود داشت. به‌روزرسانی شد.'))
            product.description = self.get_product_description()
            product.short_description = 'ابزار ساده و کاربردی برای استخراج و جمع‌آوری داده‌های املاک از وب‌سایت دیوار در فایل اکسل'
            product.features = self.get_product_features()
            product.save()
        
        # اضافه کردن فایل دانلود
        zip_path = os.path.join(settings.BASE_DIR, 'files', 'Divar-Basic-V1-Install.zip')
        if os.path.exists(zip_path):
            import shutil
            media_path = os.path.join(settings.MEDIA_ROOT, 'products')
            os.makedirs(media_path, exist_ok=True)
            dest_path = os.path.join(media_path, 'Divar-Basic-V1-Install.zip')
            
            # کپی فایل
            shutil.copy2(zip_path, dest_path)
            
            # ذخیره مسیر فایل در مدل
            from django.core.files import File
            with open(dest_path, 'rb') as f:
                product.download_file.save('Divar-Basic-V1-Install.zip', File(f), save=True)
            
            self.stdout.write(self.style.SUCCESS('فایل دانلود اضافه شد.'))
        else:
            self.stdout.write(self.style.ERROR(f'فایل ZIP یافت نشد: {zip_path}'))
            self.stdout.write(self.style.WARNING('می‌توانید بعداً فایل را از پنل ادمین آپلود کنید.'))
        
        # ایجاد پلن لایسنس یک‌سیستمی مادام‌العمر
        plan_data = {
            'name': 'لایسنس یک‌سیستمی مادام‌العمر',
            'plan_type': 'lifetime',
            'price': 200000,  # قیمت پایین‌تر از نسخه حرفه‌ای
            'max_activations': 1,
            'order': 1,
        }
        
        plan, created = LicensePlan.objects.get_or_create(
            product=product,
            name=plan_data['name'],
            defaults=plan_data
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'پلن "{plan.name}" ایجاد شد.'))
        else:
            self.stdout.write(self.style.WARNING(f'پلن "{plan.name}" از قبل وجود داشت.'))
            # به‌روزرسانی قیمت در صورت تغییر
            if plan.price != plan_data['price']:
                plan.price = plan_data['price']
                plan.save()
                self.stdout.write(self.style.SUCCESS(f'قیمت پلن به‌روزرسانی شد.'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ محصول نسخه پایه با موفقیت وارد شد!'))
        self.stdout.write(self.style.SUCCESS(f'شناسه محصول: {product.id}'))
        self.stdout.write(self.style.SUCCESS(f'نامک: {product.slug}'))
        self.stdout.write(self.style.SUCCESS(f'تعداد پلن‌ها: {product.plans.count()}'))

    def get_product_description(self):
        """توضیحات محصول نسخه پایه"""
        return """
        <h2>ربات هوشمند تحلیل املاک دیوار - نسخه پایه V1.0</h2>
        
        <p>نسخه پایه ربات تحلیل املاک دیوار، یک ابزار ساده و کاربردی برای استخراج و جمع‌آوری داده‌های آگهی‌های املاک از وب‌سایت دیوار است. این نسخه برای کاربرانی طراحی شده که نیاز به ابزار ساده و سریع برای جمع‌آوری اطلاعات املاک دارند.</p>
        
        <h3>ویژگی‌های اصلی:</h3>
        <ul>
            <li><strong>استخراج داده‌ها:</strong> استخراج اطلاعات آگهی‌های املاک از وب‌سایت دیوار</li>
            <li><strong>جمع‌آوری در فایل اکسل:</strong> ذخیره تمام داده‌های استخراج شده در فایل اکسل به صورت فایلینگ و منظم</li>
            <li><strong>سادگی استفاده:</strong> رابط کاربری ساده و قابل فهم</li>
            <li><strong>سرعت بالا:</strong> استخراج سریع داده‌ها</li>
        </ul>
        
        <h3>کاربردها:</h3>
        <ul>
            <li>جمع‌آوری اطلاعات آگهی‌های املاک</li>
            <li>تهیه لیست املاک موجود</li>
            <li>ذخیره اطلاعات در فایل اکسل برای تحلیل دستی</li>
            <li>ایجاد بانک اطلاعاتی ساده از آگهی‌های دیوار</li>
        </ul>
        
        <h3>تفاوت با نسخه حرفه‌ای:</h3>
        <p>نسخه پایه فقط قابلیت استخراج داده‌ها و ذخیره در فایل اکسل را دارد و شامل ویژگی‌های پیشرفته مانند تحلیل آماری، نمودارها، نمایش نقشه و ابزارهای تحلیلی نمی‌شود.</p>
        
        <p><strong>برای دسترسی به تمام ویژگی‌های پیشرفته، نسخه حرفه‌ای را انتخاب کنید.</strong></p>
        """

    def get_product_features(self):
        """امکانات محصول نسخه پایه"""
        return [
            "استخراج داده‌های آگهی‌های املاک از دیوار",
            "ذخیره اطلاعات در فایل اکسل به صورت فایلینگ",
            "استخراج اطلاعات پایه: قیمت، متراژ، آدرس",
            "رابط کاربری ساده و کاربردی",
            "سرعت بالا در استخراج داده‌ها",
            "خروجی Excel منظم و قابل استفاده",
        ]

