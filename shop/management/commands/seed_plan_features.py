"""پر کردن tagline و features پلن‌های ربات از کاتالوگ."""
from django.core.management.base import BaseCommand

from shop.bot_catalog import BOT_PRODUCT_SLUG, bot_plan_marketing_for_plan
from shop.models import LicensePlan, Product


class Command(BaseCommand):
    help = 'تنظیم tagline و features تمام پلن‌های ربات استخراج'

    def handle(self, *args, **options):
        product = Product.objects.filter(slug=BOT_PRODUCT_SLUG).first()
        if not product:
            self.stderr.write(self.style.ERROR('محصول ربات یافت نشد — ابتدا sync_bot_product را اجرا کنید.'))
            return

        updated = 0
        for plan in LicensePlan.objects.filter(product=product, is_active=True):
            marketing = bot_plan_marketing_for_plan(
                plan.plan_type,
                plan.allow_bulk_purchase,
                plan.order,
            )
            if not marketing.get('tagline') and not marketing.get('features'):
                self.stdout.write(self.style.WARNING(f'  بدون محتوا: {plan.name} (order={plan.order})'))
                continue

            plan.tagline = marketing['tagline']
            plan.features = marketing['features']
            plan.save(update_fields=['tagline', 'features'])
            updated += 1
            self.stdout.write(f'  updated plan id={plan.pk} order={plan.order}')

        self.stdout.write(self.style.SUCCESS(f'Done: {updated} plans updated.'))
