"""اعتبارسنجی سرور ثبت پیشنهاد ملک."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm import apply_property_suggestions
from workspace.services.crm_property_suggestions import resolve_property_suggestion_items

User = get_user_model()


class PropertySuggestionResolveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124446666', phone='09124446666', password='x')
        self.other = User.objects.create_user(username='09127778888', phone='09127778888', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09124446666',
            customer_type='خریدار',
            budget_min=5_000_000_000,
            budget_max=15_000_000_000,
            areas='ونک',
        )
        self.sale = CRMProperty.objects.create(
            user=self.user,
            title='فروش',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )
        self.rent_only = CRMProperty.objects.create(
            user=self.user,
            title='اجاره',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=200_000_000,
            monthly_rent=15_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )
        self.archived = CRMProperty.objects.create(
            user=self.user,
            title='بایگانی',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            publish_status='بایگانی',
            sale_price=8_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=80,
        )

    def test_rejects_incompatible_deal_for_buyer(self):
        ok, fails = resolve_property_suggestion_items(
            self.user, self.buyer, [{'source': 'crm', 'property_id': self.rent_only.pk}],
        )
        self.assertEqual(ok, [])
        self.assertTrue(fails)

    def test_rejects_archived_property(self):
        ok, fails = resolve_property_suggestion_items(
            self.user, self.buyer, [{'source': 'crm', 'property_id': self.archived.pk}],
        )
        self.assertEqual(ok, [])
        self.assertEqual(fails[0]['code'], 'inactive')

    def test_rejects_foreign_property(self):
        foreign = CRMProperty.objects.create(
            user=self.other,
            title='غیرمجاز',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )
        ok, fails = resolve_property_suggestion_items(
            self.user, self.buyer, [{'source': 'crm', 'property_id': foreign.pk}],
        )
        self.assertEqual(ok, [])
        self.assertEqual(fails[0]['code'], 'not_found')

    def test_apply_uses_server_score_not_client_score(self):
        text, linked = apply_property_suggestions(
            self.buyer,
            self.user,
            [{
                'source': 'crm',
                'property_id': self.sale.pk,
                'score': 100,
                'title': 'عنوان جعلی',
            }],
        )
        self.assertEqual(linked, 1)
        self.assertIn(self.sale.title, text)
        self.assertNotIn('عنوان جعلی', text)
