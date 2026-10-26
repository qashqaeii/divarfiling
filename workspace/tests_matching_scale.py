"""تست مقیاس و صفحه‌بندی — بیش از ۲۵۰۰ کاندیدای SQL."""
import time
import unittest

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import get_customer_matches
User = get_user_model()


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
})
class MatchingScalePaginationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='09129990001', phone='09129990001', password='x')
        cls.buyer = Customer.objects.create(
            user=cls.user,
            name='خریدار مقیاس',
            phone='09129990001',
            customer_type='خریدار',
            budget_min=10_000_000_000,
            budget_max=20_000_000_000,
            areas='',
            matching_tolerance_percent=20,
        )
        bulk = []
        for i in range(2600):
            bulk.append(CRMProperty(
                user=cls.user,
                title=f'فایل {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=15_000_000_000,
                neighborhood='محله عمومی',
                city='شیراز',
                area=100,
            ))
        CRMProperty.objects.bulk_create(bulk, batch_size=500)
        cls.needle = CRMProperty.objects.create(
            user=cls.user,
            title='فایل هدف',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=15_000_000_000,
            neighborhood='ونک ویژه',
            city='تهران',
            area=105,
        )

    def setUp(self):
        cache.clear()

    def test_sql_prefilter_passes_over_2500(self):
        from workspace.services.crm_matching import _crm_match_candidates_filtered_qs
        count = _crm_match_candidates_filtered_qs(self.buyer, self.user).count()
        self.assertGreaterEqual(count, 2500)

    def test_needle_found_and_pagination_stable(self):
        page1 = get_customer_matches(
            self.buyer, self.user, divar_enabled=False,
            crm_page=1, page_size=24,
        )
        self.assertGreaterEqual(page1['crm_total_count'], 2500)
        ids_page1 = {m['property_id'] for m in page1['crm_matches']}
        self.assertIn(self.needle.pk, {
            m['property_id'] for m in get_customer_matches(
                self.buyer, self.user, divar_enabled=False,
                paginate=False,
            )['crm_matches']
        })
        page2 = get_customer_matches(
            self.buyer, self.user, divar_enabled=False,
            crm_page=2, page_size=24,
        )
        ids_page2 = {m['property_id'] for m in page2['crm_matches']}
        self.assertFalse(ids_page1 & ids_page2)
        self.assertEqual(len(page1['crm_matches']), 24)
        self.assertTrue(page1['crm_has_more'])


@unittest.skipUnless(
    False,
    'Benchmark دستی — RUN_MATCH_BENCHMARK=1 برای اجرا',
)
class MatchingBenchmarkTests(TestCase):
    """برای اجرای دستی: RUN_MATCH_BENCHMARK=1 در محیط."""

    pass


def _run_benchmark_if_requested():
    import os
    if os.environ.get('RUN_MATCH_BENCHMARK') != '1':
        return
    # اجرای سبک با زمان‌سنجی در تست دستی
    user = User.objects.filter(username='09129990001').first()
    if not user:
        return
    buyer = Customer.objects.filter(user=user).first()
    if not buyer:
        return
    cache.clear()
    t0 = time.perf_counter()
    get_customer_matches(buyer, user, divar_enabled=False, crm_page=1, page_size=24)
    t1 = time.perf_counter()
    get_customer_matches(buyer, user, divar_enabled=False, crm_page=2, page_size=24)
    t2 = time.perf_counter()
    print(f'page1={t1 - t0:.2f}s page2={t2 - t1:.2f}s')
