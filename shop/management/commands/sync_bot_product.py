"""همگام‌سازی محصول واحد ربات استخراج و غیرفعال‌سازی محصولات قدیمی."""
import os
import shutil

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from shop.bot_catalog import BOT_PRODUCT_SLUG, bot_license_plans, bot_product_defaults
from shop.models import LicensePlan, Product


class Command(BaseCommand):
    help = 'ایجاد/به‌روزرسانی محصول واحد ربات استخراج دیوار'

    def handle(self, *args, **options):
        defaults = bot_product_defaults()
        product, created = Product.objects.update_or_create(
            slug=BOT_PRODUCT_SLUG,
            defaults=defaults,
        )
        action = 'ایجاد' if created else 'به‌روزرسانی'
        self.stdout.write(self.style.SUCCESS(f'محصول «{product.title}» {action} شد.'))

        # غیرفعال کردن سایر محصولات
        deactivated = Product.objects.exclude(pk=product.pk).filter(is_active=True).update(is_active=False)
        if deactivated:
            self.stdout.write(self.style.WARNING(f'{deactivated} محصول قدیمی غیرفعال شد.'))

        self._attach_installer(product)
        self._ensure_plans(product)
        self.stdout.write(self.style.SUCCESS(f'نامک: {product.slug} | پلن‌ها: {product.plans.filter(is_active=True).count()}'))

    def _attach_installer(self, product):
        candidates = [
            os.path.join(settings.BASE_DIR, 'files', 'DivarFilingExtractor_Setup_1.0.0.zip'),
            os.path.join(
                settings.BASE_DIR.parent,
                'extractor-app',
                'release',
                'installer-out',
                'DivarFilingExtractor_Setup_1.0.0.zip',
            ),
            os.path.join(settings.BASE_DIR, 'files', 'Divar-Real-Estate-Install.zip'),
            os.path.join(settings.BASE_DIR, 'files', 'Divar-Basic-V1-Install.zip'),
            os.path.join(settings.BASE_DIR, 'files', 'Robot.zip'),
            os.path.join(settings.BASE_DIR, 'Robot.zip'),
        ]
        zip_path = next(
            (p for p in candidates if os.path.exists(p) and os.path.getsize(p) >= 1024),
            None,
        )
        if not zip_path:
            self.stdout.write(self.style.WARNING('فایل نصب یافت نشد — Robot.zip را در django/files/ قرار دهید.'))
            return
        media_path = os.path.join(settings.MEDIA_ROOT, 'products')
        os.makedirs(media_path, exist_ok=True)
        filename = os.path.basename(zip_path)
        dest_path = os.path.join(media_path, filename)
        shutil.copy2(zip_path, dest_path)
        with open(dest_path, 'rb') as f:
            product.download_file.save(filename, File(f), save=True)
        self.stdout.write(self.style.SUCCESS(f'فایل نصب: {filename} ({os.path.getsize(zip_path):,} بایت)'))

    def _ensure_plans(self, product):
        plans = bot_license_plans()
        active_names = []
        for data in plans:
            active_names.append(data['name'])
            plan, created = LicensePlan.objects.update_or_create(
                product=product,
                name=data['name'],
                defaults={**data, 'is_active': True},
            )
            label = 'ایجاد' if created else 'به‌روز'
            self.stdout.write(f'  پلن {plan.name}: {label} — {plan.price:,} تومان')
        deactivated = product.plans.exclude(name__in=active_names).update(is_active=False)
        if deactivated:
            self.stdout.write(self.style.WARNING(f'  {deactivated} پلن قدیمی غیرفعال شد.'))

        from licenses.models import License

        bumped = License.objects.filter(
            order__product=product,
            max_activations=1,
        ).update(max_activations=2)
        if bumped:
            self.stdout.write(self.style.SUCCESS(f'  {bumped} لایسنس موجود به ۲ اسلات (ویندوز+اندروید) ارتقا یافت.'))
