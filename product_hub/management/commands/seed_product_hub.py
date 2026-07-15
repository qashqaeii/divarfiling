from django.core.management.base import BaseCommand

from product_hub.services.seed import seed_product_hub


class Command(BaseCommand):
    help = 'Seed کاتالوگ قابلیت‌ها و نسخه‌های نمونه مرکز توسعه'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset-features', action='store_true',
            help='حذف و جایگزینی کامل قابلیت‌ها',
        )
        parser.add_argument(
            '--reset-releases', action='store_true',
            help='حذف و جایگزینی نسخه‌های نمونه',
        )

    def handle(self, *args, **options):
        result = seed_product_hub(
            reset_features=options['reset_features'],
            reset_releases=options['reset_releases'],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Features +{result['features_created']} / ~{result['features_updated']}, "
            f"Releases +{result['releases_created']}"
        ))
