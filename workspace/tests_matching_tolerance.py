"""تست انعطاف‌پذیری قابل‌تنظیم تطبیق هوشمند."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import (
    get_customer_matches,
    normalize_matching_tolerance_percent,
    profile_tolerance_ratio,
)

User = get_user_model()


class MatchingToleranceNormalizeTests(TestCase):
    def test_default_and_valid_steps(self):
        self.assertEqual(normalize_matching_tolerance_percent(None), 20)
        self.assertEqual(normalize_matching_tolerance_percent(0), 0)
        self.assertEqual(normalize_matching_tolerance_percent(25), 25)
        self.assertEqual(normalize_matching_tolerance_percent(50), 50)

    def test_rejects_out_of_range_and_non_step(self):
        with self.assertRaises(ValueError):
            normalize_matching_tolerance_percent(-5)
        with self.assertRaises(ValueError):
            normalize_matching_tolerance_percent(55)
        with self.assertRaises(ValueError):
            normalize_matching_tolerance_percent(22)
        with self.assertRaises(ValueError):
            normalize_matching_tolerance_percent('abc')


class MatchingToleranceBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09124445555', phone='09124445555', password='x',
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار تلورانس',
            phone='09124445555',
            customer_type='خریدار',
            budget_min=10_000_000_000,
            budget_max=15_000_000_000,
            min_area=80,
            max_area=120,
            areas='ونک',
            matching_tolerance_percent=20,
        )
        self.in_range = CRMProperty.objects.create(
            user=self.user,
            title='داخل بودجه',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=13_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            rooms='2',
        )
        self.slight_over = CRMProperty.objects.create(
            user=self.user,
            title='کمی بالای بودجه',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=16_500_000_000,  # ۱۰٪ بالای ۱۵ میلیارد
            neighborhood='ونک',
            city='تهران',
            area=110,
            rooms='2',
        )
        self.far_over = CRMProperty.objects.create(
            user=self.user,
            title='خیلی بالای بودجه',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=20_000_000_000,  # ~۳۳٪ بالای ۱۵ میلیارد
            neighborhood='ونک',
            city='تهران',
            area=100,
            rooms='2',
        )

    def test_profile_tolerance_ratio_from_customer(self):
        self.buyer.matching_tolerance_percent = 35
        self.assertAlmostEqual(profile_tolerance_ratio(self.buyer), 0.35)

    def test_default_tolerance_includes_slight_excludes_far(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertIn(self.in_range.title, titles)
        self.assertIn(self.slight_over.title, titles)
        self.assertNotIn(self.far_over.title, titles)
        self.assertEqual(data['matching_tolerance_percent'], 20)

    def test_zero_tolerance_excludes_over_budget(self):
        self.buyer.matching_tolerance_percent = 0
        self.buyer.save(update_fields=['matching_tolerance_percent'])
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertIn(self.in_range.title, titles)
        self.assertNotIn(self.slight_over.title, titles)
        self.assertNotIn(self.far_over.title, titles)
        self.assertEqual(data['matching_tolerance_percent'], 0)

    def test_high_tolerance_includes_far_over(self):
        self.buyer.matching_tolerance_percent = 50
        self.buyer.save(update_fields=['matching_tolerance_percent'])
        data = get_customer_matches(self.buyer, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertIn(self.far_over.title, titles)
        self.assertEqual(data['matching_tolerance_percent'], 50)
        far = next(m for m in data['crm_matches'] if m['title'] == self.far_over.title)
        self.assertTrue(any('بالای بودجه' in r for r in far['reasons']))
        in_range = next(m for m in data['crm_matches'] if m['title'] == self.in_range.title)
        self.assertGreaterEqual(in_range['score'], far['score'])


class MatchingToleranceApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09126667777', phone='09126667777', password='x',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.buyer = Customer.objects.create(
            user=self.user,
            name='مخاطب API',
            phone='09126667777',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=8_000_000_000,
            matching_tolerance_percent=20,
        )
        self.url = reverse(
            'workspace:crm_contact_matching_tolerance',
            kwargs={'customer_id': self.buyer.pk},
        )

    def test_save_tolerance_and_return_matches_html(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'matching_tolerance_percent': 35}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['matching_tolerance_percent'], 35)
        self.assertIn('matches_html', data)
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.matching_tolerance_percent, 35)

    def test_rejects_invalid_tolerance(self):
        res = self.client.post(
            self.url,
            data=json.dumps({'matching_tolerance_percent': 33}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['ok'])
        self.buyer.refresh_from_db()
        self.assertEqual(self.buyer.matching_tolerance_percent, 20)
