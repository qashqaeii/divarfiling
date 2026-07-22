"""ادغام لیست‌های سرنخ تکراری همان منطقه."""
from django.core.management.base import BaseCommand

from accounts.services.lead_import import merge_duplicate_region_lists


class Command(BaseCommand):
    help = 'Merge LeadList rows that share the same city/district/category into one regional list.'

    def handle(self, *args, **options):
        result = merge_duplicate_region_lists()
        self.stdout.write(self.style.SUCCESS(str(result)))
