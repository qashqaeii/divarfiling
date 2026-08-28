"""Tests for live homepage display stats (DB × multiplier)."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from shop.bot_catalog import (
    HOME_STATS_DISPLAY_MULTIPLIER,
    HOME_STATS_LICENSES_EXTRA_MULTIPLIER,
    home_display_stats,
)
from shop.models import LicensePlan, Order, Product


class HomeDisplayStatsTests(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.user = User.objects.create_user(username='stat_user', password='x')
        self.product = Product.objects.create(
            title='Bot',
            slug='divar-extraction-bot-stats',
            description='test',
            is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product,
            name='Monthly',
            plan_type='monthly',
            duration_days=30,
            price=1000,
            is_active=True,
        )

    def test_counts_are_live_and_multiplied(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=1000,
            status='paid',
            paid_at=timezone.now(),
        )
        from licenses.models import License

        License.objects.create(
            order=order,
            plan=self.plan,
            license_key='TEST-LIVE-KEY-001',
            status='active',
            max_activations=1,
        )

        stats = home_display_stats()
        self.assertTrue(stats['is_live'])
        self.assertEqual(stats['display_multiplier'], HOME_STATS_DISPLAY_MULTIPLIER)
        self.assertEqual(stats['raw']['total_orders'], 1)
        self.assertEqual(stats['total_orders'], 1 * HOME_STATS_DISPLAY_MULTIPLIER)
        self.assertEqual(stats['raw']['total_licenses'], 1)
        self.assertEqual(
            stats['total_licenses'],
            1 * HOME_STATS_DISPLAY_MULTIPLIER * HOME_STATS_LICENSES_EXTRA_MULTIPLIER,
        )
        self.assertGreaterEqual(stats['total_users'], 1 * HOME_STATS_DISPLAY_MULTIPLIER)
        self.assertGreaterEqual(stats['satisfaction_rate'], 1)
        self.assertLessEqual(stats['satisfaction_rate'], 99)
        self.assertIn('uptime_label', stats)
        self.assertIn('uptime_total_seconds', stats)
        self.assertGreaterEqual(stats['uptime_total_seconds'], 0)
        if stats['uptime_label']:
            self.assertRegex(stats['uptime_label'], r'[۰-۹]')
            self.assertIn('دقیقه', stats['uptime_label'])
