"""تست context builder خلاصه آگهی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_workspace.context_builders import listing_context
from workspace.models import Dataset, Listing


class ListingContextTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='ctxuser', password='pass', phone='09121112222',
        )
        self.dataset = Dataset.objects.create(
            user=user,
            name='تست',
            original_filename='t.xlsx',
            file_format='xlsx',
            city='تهران',
            transaction_type='rent',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='tok1',
            title='آپارتمان ۹۰ متری جیحون',
            neighborhood='جیحون',
            city='تهران',
            area=90,
            rooms='2',
            deposit=1_200_000_000,
            rent=0,
            data={
                'طبقه': '۶',
                'ساخت': '1394',
                'پارکینگ': 'دارد',
                'انباری': 'دارد',
            },
        )

    def test_build_includes_tab_sections_and_benchmark(self):
        benchmark = {
            'label': 'رهن کامل معادل',
            'price_per_sqm_fmt': '1.2 میلیارد تومان',
            'market_median_fmt': '805 میلیون تومان',
            'diff_pct': -16.8,
            'verdict': 'زیر بازار — فرصت مناسب برای مشتری',
            'note': 'رهن کامل — مقایسه بر اساس رهن کامل معادل',
        }
        ctx = listing_context.build(self.listing, self.dataset, benchmark)

        self.assertIn('ودیعه', ctx['tab_financial'])
        self.assertIn('متراژ', ctx['tab_property'])
        self.assertIn('جیحون', ctx['tab_location'] + ctx['neighborhood'])
        self.assertIn('پارکینگ', ctx['tab_features'])
        self.assertEqual(ctx['benchmark']['market_median'], '805 میلیون تومان')
        self.assertEqual(ctx['benchmark']['diff_pct'], '-16.8٪')
        self.assertEqual(ctx['benchmark_verdict'], benchmark['verdict'])
