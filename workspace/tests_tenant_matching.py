"""تست تطبیق مستاجر — فقط فایل‌های رهن/اجاره در بازه بودجه."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm_match_notifications import contact_matches_payload
from workspace.services.crm_matching import get_customer_matches

User = get_user_model()


class TenantMatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123339999', phone='09123339999', password='x')
        self.tenant = Customer.objects.create(
            user=self.user,
            name='مستاجر تست',
            phone='09123339999',
            customer_type='مستاجر',
            status='در حال پیگیری',
            deposit_min=200_000_000,
            deposit_max=350_000_000,
            rent_min=17_000_000,
            rent_max=20_000_000,
            areas='ونک',
        )
        self.sale_file = CRMProperty.objects.create(
            user=self.user,
            title='همکف ۳۱۴ متری حیاط اختصاصی',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=11_300_000_000,
            neighborhood='ونک',
            city='تهران',
            area=314,
        )
        self.rent_match = CRMProperty.objects.create(
            user=self.user,
            title='اجاره ونک ۹۰ متری',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=250_000_000,
            monthly_rent=18_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='2',
        )
        self.rent_out_of_budget = CRMProperty.objects.create(
            user=self.user,
            title='اجاره گران',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=800_000_000,
            monthly_rent=45_000_000,
            neighborhood='ونک',
            city='تهران',
            area=120,
        )

    def test_tenant_does_not_see_sale_files(self):
        data = get_customer_matches(self.tenant, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertNotIn(self.sale_file.title, titles)

    def test_tenant_sees_rent_file_in_budget(self):
        data = get_customer_matches(self.tenant, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertIn(self.rent_match.title, titles)
        self.assertEqual(data['total_count'], len(data['crm_matches']) + len(data['divar_matches']))

    def test_buyer_does_not_see_rent_only_files(self):
        buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09120001111',
            customer_type='خریدار',
            budget_min=3_000_000_000,
            budget_max=6_000_000_000,
        )
        data = get_customer_matches(buyer, self.user, divar_enabled=False)
        titles = [m['title'] for m in data['crm_matches']]
        self.assertIn(self.sale_file.title, titles)
        self.assertNotIn(self.rent_match.title, titles)

    def test_total_count_zero_when_no_matches(self):
        CRMProperty.objects.filter(user=self.user).delete()
        data = get_customer_matches(self.tenant, self.user, divar_enabled=False)
        self.assertEqual(data['total_count'], 0)
        self.assertEqual(data['total_count'], len(data['crm_matches']) + len(data['divar_matches']))
        payload = contact_matches_payload(self.user, self.tenant.pk)
        self.assertEqual(payload['total_count'], 0)
