"""لینک‌های اتوماسیون رشد — بدون /pricing/."""
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.services.growth_links import bot_buy_landing_url, renewal_or_buy_landing_url
from shop.models import Product


@override_settings(SITE_URL='https://divarfiling.ir', LICENSE_RENEWAL_LANDING_URL='')
class GrowthLinksDefaultTests(TestCase):
    def test_renewal_url_uses_bot_buy_path(self):
        Product.objects.create(
            title='ربات استخراج دیوار',
            slug='divar-extraction-bot',
            description='test',
            is_active=True,
        )
        buy_path = reverse('buy', kwargs={'slug': 'divar-extraction-bot'})
        expected = f'https://divarfiling.ir{buy_path}'
        self.assertEqual(renewal_or_buy_landing_url(), expected)
        self.assertEqual(bot_buy_landing_url(), expected)

    @override_settings(LICENSE_RENEWAL_LANDING_URL='https://example.com/custom/')
    def test_explicit_setting_overrides_buy_url(self):
        self.assertEqual(renewal_or_buy_landing_url(), 'https://example.com/custom/')
