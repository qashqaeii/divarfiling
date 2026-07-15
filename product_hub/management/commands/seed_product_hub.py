from django.core.management.base import BaseCommand

from product_hub.services.seed import seed_product_hub


class Command(BaseCommand):
    help = 'Seed فقط کاتالوگ قابلیت‌های واقعی سیستم (بدون داده فیک)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-features', action='store_true',
            help='حذف و جایگزینی کامل کاتالوگ قابلیت‌ها',
        )
        parser.add_argument(
            '--keep-fake', action='store_true',
            help='پیشنهاد/باگ/نسخه‌های نمونه قبلی را پاک نکن',
        )

    def handle(self, *args, **options):
        result = seed_product_hub(
            reset_features=options['reset_features'],
            purge_fake=not options['keep_fake'],
        )
        purged = result['purged']
        self.stdout.write(self.style.SUCCESS(
            f"Features +{result['features_created']} / ~{result['features_updated']} "
            f"(total {result['features_total']}, removed {result.get('features_removed', 0)}), "
            f"published releases left: {result['releases_total']}, "
            f"purged fake: requests={purged['requests']} bugs={purged['bugs']} "
            f"releases={purged['releases']} users={purged['users']}"
        ))
