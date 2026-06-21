"""
دستور مدیریتی برای وارد کردن محصول نسخه حرفه‌ای
"""
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from shop.models import Product, ProductMedia, LicensePlan


class Command(BaseCommand):
    help = 'وارد کردن محصول نسخه حرفه‌ای ربات دیوار'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('شروع وارد کردن محصول...'))
        
        # ایجاد محصول نسخه حرفه‌ای
        product, created = Product.objects.get_or_create(
            slug='professional',
            defaults={
                'title': 'ربات هوشمند تحلیل املاک دیوار - نسخه حرفه‌ای',
                'description': self.get_product_description(),
                'short_description': 'ابزاری قدرتمند برای استخراج، پردازش و تحلیل داده‌های املاک از وب‌سایت دیوار',
                'features': self.get_product_features(),
                'is_active': True,
                'order': 1,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'محصول "{product.title}" ایجاد شد.'))
        else:
            self.stdout.write(self.style.WARNING(f'محصول "{product.title}" از قبل وجود داشت. به‌روزرسانی شد.'))
            product.description = self.get_product_description()
            product.short_description = 'ابزاری قدرتمند برای استخراج، پردازش و تحلیل داده‌های املاک از وب‌سایت دیوار'
            product.features = self.get_product_features()
            product.save()
        
        # اضافه کردن فایل دانلود
        zip_path = os.path.join(settings.BASE_DIR, 'files', 'Divar-Real-Estate-Install.zip')
        if os.path.exists(zip_path):
            import shutil
            media_path = os.path.join(settings.MEDIA_ROOT, 'products')
            os.makedirs(media_path, exist_ok=True)
            dest_path = os.path.join(media_path, 'Divar-Real-Estate-Install.zip')
            
            # کپی فایل
            shutil.copy2(zip_path, dest_path)
            
            # ذخیره مسیر فایل در مدل
            from django.core.files import File
            with open(dest_path, 'rb') as f:
                product.download_file.save('Divar-Real-Estate-Install.zip', File(f), save=True)
            
            self.stdout.write(self.style.SUCCESS('فایل دانلود اضافه شد.'))
        else:
            self.stdout.write(self.style.ERROR(f'فایل ZIP یافت نشد: {zip_path}'))
            self.stdout.write(self.style.WARNING('می‌توانید بعداً فایل را از پنل ادمین آپلود کنید.'))
        
        # ایجاد پلن‌های لایسنس
        plans_data = [
            {
                'name': 'لایسنس یک‌سیستمی مادام‌العمر',
                'plan_type': 'lifetime',
                'price': 500000,
                'max_activations': 1,
                'order': 1,
            },
            {
                'name': 'لایسنس یک‌سیستمی سالانه',
                'plan_type': 'yearly',
                'price': 200000,
                'duration_days': 365,
                'max_activations': 1,
                'order': 2,
            },
            {
                'name': 'لایسنس یک‌سیستمی ماهانه',
                'plan_type': 'monthly',
                'price': 50000,
                'duration_days': 30,
                'max_activations': 1,
                'order': 3,
            },
        ]
        
        for plan_data in plans_data:
            plan, created = LicensePlan.objects.get_or_create(
                product=product,
                name=plan_data['name'],
                defaults=plan_data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'پلن "{plan.name}" ایجاد شد.'))
            else:
                self.stdout.write(self.style.WARNING(f'پلن "{plan.name}" از قبل وجود داشت.'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ محصول با موفقیت وارد شد!'))
        self.stdout.write(self.style.SUCCESS(f'شناسه محصول: {product.id}'))
        self.stdout.write(self.style.SUCCESS(f'نامک: {product.slug}'))
        self.stdout.write(self.style.SUCCESS(f'تعداد پلن‌ها: {product.plans.count()}'))

    def get_product_description(self):
        """استخراج توضیحات محصول از فایل امکانات"""
        return """
        <h2>ربات هوشمند تحلیل املاک دیوار - نسخه حرفه‌ای</h2>
        
        <p>این نسخه حرفه‌ای از ربات تحلیل املاک دیوار، ابزاری قدرتمند و کامل برای مشاوران املاک، تحلیل‌گران بازار و علاقه‌مندان به داده‌های املاک است.</p>
        
        <h3>ویژگی‌های اصلی:</h3>
        <ul>
            <li><strong>استخراج خودکار داده‌ها:</strong> استخراج کامل اطلاعات آگهی‌های املاک از وب‌سایت دیوار با پردازش موازی</li>
            <li><strong>پشتیبانی از 5 نوع معامله:</strong> فروش مسکونی، اجاره مسکونی، فروش اداری و تجاری، اجاره اداری و تجاری، پروژه‌های ساخت‌وساز</li>
            <li><strong>فیلتر پیشرفته:</strong> فیلتر بر اساس استان، شهر، محله، نوع معامله و زیردسته‌بندی</li>
            <li><strong>تحلیل آماری:</strong> آمار توصیفی، شناسایی داده‌های پرت، محاسبه قیمت هر متر مربع</li>
            <li><strong>نمودارهای تحلیلی:</strong> نمودار توزیع قیمت، متراژ، پراکندگی و Box Plot</li>
            <li><strong>نمایش نقشه:</strong> نمایش تمام آگهی‌ها روی نقشه با تفکیک بصری مشاور و شخصی</li>
            <li><strong>خروجی‌های متعدد:</strong> Excel، CSV، JSON با فرمت‌بندی حرفه‌ای</li>
            <li><strong>دانلود تصاویر:</strong> دانلود خودکار تمام تصاویر آگهی‌ها</li>
            <li><strong>ابزارهای کاربردی:</strong> تبدیل رهن و اجاره، تبدیل واحدها، محاسبات مالی</li>
        </ul>
        
        <h3>رابط کاربری:</h3>
        <ul>
            <li>رابط کاربری مدرن با CustomTkinter</li>
            <li>پشتیبانی از تم روشن و تاریک</li>
            <li>طراحی Responsive</li>
            <li>رابط کاربری چندزبانه (فارسی/انگلیسی)</li>
        </ul>
        
        <h3>کاربردها:</h3>
        <ul>
            <li>تحلیل بازار املاک</li>
            <li>مقایسه قیمت‌ها در مناطق مختلف</li>
            <li>یافتن فرصت‌های سرمایه‌گذاری</li>
            <li>تهیه گزارش‌های تحلیلی</li>
            <li>مدیریت اطلاعات مشتریان</li>
        </ul>
        """

    def get_product_features(self):
        """استخراج امکانات محصول از فایل امکانات"""
        return [
            "استخراج خودکار داده‌های آگهی‌های املاک از دیوار",
            "پردازش موازی (Multi-threading) برای سرعت بالا",
            "پشتیبانی از 5 نوع معامله اصلی",
            "فیلتر پیشرفته بر اساس استان، شهر، محله",
            "استخراج اطلاعات کامل: قیمت، متراژ، اتاق، طبقه، امکانات",
            "دانلود خودکار تصاویر آگهی‌ها",
            "نمایش نقشه تعاملی با Folium",
            "تحلیل آماری پیشرفته (میانگین، میانه، انحراف معیار)",
            "نمودارهای تحلیلی (Histogram, Scatter Plot, Box Plot)",
            "خروجی Excel با فرمت‌بندی حرفه‌ای",
            "خروجی CSV و JSON",
            "تبدیل رهن و اجاره",
            "تبدیل واحدها (متر به فوت)",
            "محاسبه قیمت هر متر مربع",
            "فیلتر هوشمند آگهی‌های همخانه",
            "تفکیک بصری آگهی‌های مشاور از شخصی در نقشه",
            "رابط کاربری مدرن با CustomTkinter",
            "پشتیبانی از تم روشن و تاریک",
            "رابط کاربری چندزبانه (فارسی/انگلیسی)",
            "سیستم نسخه‌بندی حرفه‌ای",
        ]

