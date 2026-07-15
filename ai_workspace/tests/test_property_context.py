"""تست context builder فایل شخصی."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_workspace.context_builders import property_context
from workspace.models import CRMProperty


class PropertyContextTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username='propctx', password='pass', phone='09123334444',
        )
        self.prop = CRMProperty.objects.create(
            user=user,
            title='آپارتمان ۹۰ متری سعادت‌آباد',
            property_type='آپارتمان',
            deal_mode='فروش',
            city='تهران',
            neighborhood='سعادت‌آباد',
            area=90,
            rooms='2',
            floor=4,
            build_year=1398,
            sale_price=12_500_000_000,
            has_parking=True,
            has_elevator=True,
            notes='نورگیر عالی',
        )

    def test_build_includes_tabs_and_benchmark(self):
        benchmark = {
            'label': 'قیمت هر متر',
            'price_per_sqm_fmt': '۱۳۸.۸ میلیون تومان',
            'market_median_fmt': '۱۵۰ میلیون تومان',
            'diff_pct': -8.2,
            'verdict': 'زیر بازار — فرصت مناسب برای مشتری',
            'note': '',
        }
        ctx = property_context.build(self.prop, benchmark)

        self.assertIn('قیمت فروش', ctx['tab_financial'])
        self.assertIn('متراژ', ctx['tab_property'])
        self.assertIn('سعادت‌آباد', ctx['tab_location'])
        self.assertIn('نورگیر عالی', ctx['tab_text'])
        self.assertEqual(ctx['benchmark']['market_median'], '۱۵۰ میلیون تومان')
        self.assertEqual(ctx['benchmark_verdict'], benchmark['verdict'])
