from django.core.management.base import BaseCommand

from product_hub.services.seed import seed_product_hub


class Command(BaseCommand):
    help = 'Seed دقیق قابلیت‌ها، changelog و داده نمونه مرکز توسعه'

    def add_arguments(self, parser):
        parser.add_argument('--reset-features', action='store_true', help='جایگزینی کامل قابلیت‌ها')
        parser.add_argument('--reset-releases', action='store_true', help='جایگزینی نسخه‌های seed')
        parser.add_argument('--no-sync-releases', action='store_true', help='changelog موجود را بازنویسی نکن')
        parser.add_argument('--no-demo', action='store_true', help='پیشنهاد/باگ نمونه ساخته نشود')

    def handle(self, *args, **options):
        result = seed_product_hub(
            reset_features=options['reset_features'],
            reset_releases=options['reset_releases'],
            sync_releases=not options['no_sync_releases'],
            with_demo=not options['no_demo'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Features +{result['features_created']} / ~{result['features_updated']} "
            f"(total {result['features_total']}), "
            f"Releases +{result['releases_created']} (total {result['releases_total']}), "
            f"Demo requests +{result['demo_requests']}, bugs +{result['demo_bugs']}"
        ))
