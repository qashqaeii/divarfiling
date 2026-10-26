"""تست موتور بازیابی کامل تطبیق — بدون سقف اسکن."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import get_customer_matches, match_crm_properties
from workspace.services.crm_matching_geo import location_tokens_equivalent

User = get_user_model()


class MatchingRetrievalNoScanCapTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880001', phone='09128880001', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار اسکن',
            phone='09128880001',
            customer_type='خریدار',
            budget_min=9_000_000_000,
            budget_max=11_000_000_000,
            min_area=90,
            max_area=110,
            areas='ونک',
            matching_tolerance_percent=5,
        )
        now = timezone.now()
        for i in range(850):
            CRMProperty.objects.create(
                user=self.user,
                title=f'ضعیف {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=25_000_000_000,
                neighborhood='نیاوران',
                city='تهران',
                area=200,
                updated_at=now - timedelta(minutes=i),
            )
        self.best_old = CRMProperty.objects.create(
            user=self.user,
            title='بهترین تطبیق',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=100,
            updated_at=now - timedelta(days=400),
        )

    def test_old_high_score_property_found_after_many_others(self):
        matches = match_crm_properties(self.buyer, self.user)
        ids = [m['property_id'] for m in matches]
        self.assertIn(self.best_old.pk, ids)


class MatchingAreasRegressionTests(TestCase):
    """بازتولید سناریوی ۴۸→صفر: محله ترجیحی vs بدون محله."""

    def setUp(self):
        self.user = User.objects.create_user(username='09128880002', phone='09128880002', password='x')
        self.base_kwargs = dict(
            user=self.user,
            name='خریدار شیراز',
            phone='09128880002',
            customer_type='خریدار',
            city='تهران',
            district='منطقه ۵',
            budget_min=13_000_000_000,
            budget_max=18_000_000_000,
            matching_tolerance_percent=20,
        )

    def _make_props(self):
        specs = [
            ('صیاد', 15_000_000_000),
            ('عدالت', 14_000_000_000),
            ('آپادانا', 16_000_000_000),
            ('دیگر', 15_500_000_000),
        ]
        created = []
        for hood, price in specs:
            created.append(CRMProperty.objects.create(
                user=self.user,
                title=hood,
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=price,
                neighborhood=hood,
                city='شیراز',
                area=120,
            ))
        created.append(CRMProperty.objects.create(
            user=self.user,
            title='شیراز بدون محله',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=15_000_000_000,
            neighborhood='',
            city='شیراز',
            area=120,
        ))
        created.append(CRMProperty.objects.create(
            user=self.user,
            title='ترکیبی',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=15_000_000_000,
            neighborhood='شیراز - محله صیاد',
            city='شیراز',
            area=120,
        ))
        return created

    def test_without_areas_includes_city_only_properties(self):
        buyer = Customer.objects.create(**self.base_kwargs, areas='')
        self._make_props()
        data = get_customer_matches(buyer, self.user, divar_enabled=False, paginate=False)
        self.assertGreaterEqual(data['total_count'], 5)

    def test_with_areas_finds_matching_neighborhoods_despite_identity_city(self):
        buyer = Customer.objects.create(
            **self.base_kwargs,
            areas='صیاد، عدالت، آپادانا',
        )
        props = self._make_props()
        data = get_customer_matches(buyer, self.user, divar_enabled=False, paginate=False)
        ids = {m['property_id'] for m in data['crm_matches']}
        self.assertGreaterEqual(data['total_count'], 3)
        for p in props[:3]:
            self.assertIn(p.pk, ids)

    def test_compound_neighborhood_string_matches(self):
        buyer = Customer.objects.create(**self.base_kwargs, areas='صیاد')
        props = self._make_props()
        compound = props[-1]
        data = get_customer_matches(buyer, self.user, divar_enabled=False, paginate=False)
        ids = {m['property_id'] for m in data['crm_matches']}
        self.assertIn(compound.pk, ids)

    def test_total_count_not_capped_at_page_size(self):
        buyer = Customer.objects.create(**self.base_kwargs, areas='')
        for i in range(30):
            CRMProperty.objects.create(
                user=self.user,
                title=f'فایل {i}',
                property_type='آپارتمان',
                deal_mode='فروش',
                transaction_status='فعال',
                sale_price=15_000_000_000,
                neighborhood='محله‌ای',
                city='شیراز',
                area=100,
            )
        data = get_customer_matches(
            buyer, self.user, divar_enabled=False, paginate=True, page_size=10, crm_page=1,
        )
        self.assertGreaterEqual(data['total_count'], 30)
        self.assertEqual(len(data['crm_matches']), 10)
        self.assertTrue(data['crm_has_more'])


class MatchingGeoCompoundTokenTests(TestCase):
    def test_compound_location_string(self):
        self.assertTrue(location_tokens_equivalent('صیاد', 'شیراز - محله صیاد'))
