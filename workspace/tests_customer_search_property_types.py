"""ترجیحات چندگانه نوع ملک — فرم، API و تطبیق."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.forms import CustomerForm
from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import (
    _profile_property_type_eligible,
    match_crm_properties,
    match_customers_for_property,
    match_divar_listings,
)
from workspace.services.customer_search_property_types import customer_search_property_types_list

User = get_user_model()


class CustomerSearchPropertyTypesFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121001001', phone='09121001001', password='x')

    def _base_form_data(self, **extra):
        data = {
            'name': 'خریدار تست',
            'phone': '09121001001',
            'customer_type': 'خریدار',
            'status': 'جدید',
            'priority': 'متوسط',
            'budget_min': '5000000000',
            'budget_max': '15000000000',
            'areas': 'ونک',
        }
        data.update(extra)
        return data

    def test_save_apartment_and_villa_retrieve(self):
        form = CustomerForm(self._base_form_data(search_property_types=['آپارتمان', 'ویلا']))
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = self.user
        customer.save()
        self.assertEqual(customer.property_types, ['آپارتمان', 'ویلا'])
        self.assertEqual(customer.property_type, '')
        self.assertEqual(customer_search_property_types_list(customer), ['آپارتمان', 'ویلا'])

    def test_edit_form_shows_saved_selections(self):
        customer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09121001002',
            customer_type='خریدار',
            property_types=['آپارتمان', 'ویلا'],
            budget_min=5_000_000_000,
            budget_max=15_000_000_000,
        )
        form = CustomerForm(instance=customer)
        self.assertEqual(form.initial.get('search_property_types'), ['آپارتمان', 'ویلا'])

    def test_clear_all_removes_restriction(self):
        customer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09121001003',
            customer_type='خریدار',
            property_type='آپارتمان',
            property_types=['آپارتمان'],
            budget_min=5_000_000_000,
            budget_max=15_000_000_000,
        )
        form = CustomerForm(self._base_form_data(), instance=customer)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.property_types, [])
        self.assertEqual(saved.property_type, '')
        self.assertFalse(customer_search_property_types_list(saved))

    def test_legacy_single_property_type_still_works(self):
        customer = Customer.objects.create(
            user=self.user,
            name='خریدار قدیمی',
            phone='09121001004',
            customer_type='خریدار',
            property_type='ویلا',
            property_types=[],
            budget_min=5_000_000_000,
            budget_max=15_000_000_000,
            areas='ونک',
        )
        self.assertEqual(customer_search_property_types_list(customer), ['ویلا'])
        self.assertTrue(_profile_property_type_eligible(customer, 'ویلا'))
        self.assertFalse(_profile_property_type_eligible(customer, 'زمین'))


class CustomerSearchPropertyTypesMatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09122002001', phone='09122002001', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار دو نوع',
            phone='09122002001',
            customer_type='خریدار',
            property_types=['آپارتمان', 'ویلا'],
            budget_min=5_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
            matching_tolerance_percent=20,
        )
        self.apt = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ونک',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=95,
            rooms='2',
        )
        self.villa = CRMProperty.objects.create(
            user=self.user,
            title='ویلا ونک',
            property_type='ویلا',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=12_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=200,
            rooms='3',
        )
        self.shop = CRMProperty.objects.create(
            user=self.user,
            title='مغازه ونک',
            property_type='مغازه',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=11_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=60,
        )
        self.dataset = Dataset.objects.create(user=self.user, name='ds', is_active=True)
        self.listing_apt = Listing.objects.create(
            dataset=self.dataset,
            token='apt-token',
            title='آپارتمان دیوار',
            price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={'property_type': 'آپارتمان'},
        )
        self.listing_land = Listing.objects.create(
            dataset=self.dataset,
            token='land-token',
            title='زمین دیوار',
            price=9_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=500,
            is_expired=False,
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            data={'property_type': 'زمین'},
        )

    def test_matches_apartment_and_villa_rejects_unrelated(self):
        crm_ids = {m['property_id'] for m in match_crm_properties(self.buyer, self.user, limit=20)}
        self.assertIn(self.apt.pk, crm_ids)
        self.assertIn(self.villa.pk, crm_ids)
        self.assertNotIn(self.shop.pk, crm_ids)

    def test_reverse_match_respects_multi_types(self):
        customer_ids = {m['customer_id'] for m in match_customers_for_property(self.apt, self.user, limit=20)}
        self.assertIn(self.buyer.pk, customer_ids)
        only_land = Customer.objects.create(
            user=self.user,
            name='فقط زمین',
            phone='09122002002',
            customer_type='خریدار',
            property_types=['زمین'],
            budget_min=5_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
        )
        customer_ids_villa = {m['customer_id'] for m in match_customers_for_property(self.villa, self.user, limit=20)}
        self.assertIn(self.buyer.pk, customer_ids_villa)
        self.assertNotIn(only_land.pk, customer_ids_villa)

    def test_divar_listing_type_filter(self):
        matches = match_divar_listings(self.buyer, self.user, limit=20, dataset_id=self.dataset.pk)
        tokens = {m['token'] for m in matches}
        self.assertIn(self.listing_apt.token, tokens)
        self.assertNotIn(self.listing_land.token, tokens)


class CustomerSearchPropertyTypesMobileApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123003001', password='test')
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار API',
            phone='09123003001',
            customer_type='خریدار',
            property_types=['آپارتمان', 'ویلا'],
            budget_min=5_000_000_000,
            budget_max=15_000_000_000,
        )

    def test_patch_without_property_types_preserves_multi(self):
        resp = self.client.patch(
            f'/api/mobile/v1/crm/contacts/{self.customer.pk}',
            {'budget_max': 16_000_000_000},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.property_types, ['آپارتمان', 'ویلا'])
        data = resp.json()['data']
        self.assertEqual(data['property_types'], ['آپارتمان', 'ویلا'])


class BuilderSearchPropertyTypesUnchangedTests(TestCase):
    def test_builder_form_still_sets_sell_property_type(self):
        form = CustomerForm({
            'name': 'سازنده',
            'phone': '09124004001',
            'customer_type': 'سازنده',
            'status': 'جدید',
            'priority': 'متوسط',
            'property_type': 'آپارتمان',
            'budget_min': '5000000000',
            'budget_max': '8000000000',
            'builder_buy_types': ['ویلا', 'زمین'],
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = User.objects.create_user(username='09124004002', phone='09124004002', password='x')
        customer = form.save(commit=False)
        customer.user = user
        customer.save()
        self.assertEqual(customer.property_type, 'آپارتمان')
        self.assertEqual(customer.property_types, [])
