"""تست نوع مخاطب سازنده و تطبیق دوگانه."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.forms import CustomerForm
from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import (
    get_builder_customer_matches,
    get_customer_matches,
    is_builder_customer,
    parse_builder_buy_types,
)

User = get_user_model()


class BuilderContactFormTests(TestCase):
    def test_customer_form_accepts_builder_profile(self):
        form = CustomerForm({
            'name': 'سازنده تست',
            'phone': '09121110000',
            'customer_type': 'سازنده',
            'status': 'جدید',
            'priority': 'متوسط',
            'property_type': 'آپارتمان',
            'budget_min': '5000000000',
            'budget_max': '8000000000',
            'areas': 'ونک، نیاوران',
            'builder_buy_types': ['ویلا', 'زمین'],
            'builder_buy_budget_min': '20000000000',
            'builder_buy_budget_max': '50000000000',
            'builder_buy_areas': 'لواسان، شهریار',
            'builder_buy_min_area': '300',
            'builder_buy_max_area': '1200',
        })
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        customer.user = User.objects.create_user(username='09121110001', phone='09121110001', password='x')
        customer.save()
        self.assertEqual(customer.property_type, 'آپارتمان')
        self.assertEqual(parse_builder_buy_types(customer.builder_buy_property_types), ['ویلا', 'زمین'])


class BuilderMatchingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09122220000', phone='09122220000', password='x')
        self.builder = Customer.objects.create(
            user=self.user,
            name='سازنده نمونه',
            phone='09122220000',
            customer_type='سازنده',
            status='در حال پیگیری',
            property_type='آپارتمان',
            budget_min=4_000_000_000,
            budget_max=7_000_000_000,
            areas='ونک',
            builder_buy_property_types='ویلا, زمین',
            builder_buy_budget_min=15_000_000_000,
            builder_buy_budget_max=40_000_000_000,
            builder_buy_areas='لواسان',
            builder_buy_min_area=400,
            builder_buy_max_area=2000,
        )
        self.apartment = CRMProperty.objects.create(
            user=self.user,
            title='آپارتمان ونک ۹۰ متری',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=5_500_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='2',
        )
        self.land = CRMProperty.objects.create(
            user=self.user,
            title='زمین لواسان ۸۰۰ متری',
            property_type='زمین',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=25_000_000_000,
            neighborhood='لواسان',
            city='تهران',
            area=800,
        )

    def test_builder_is_match_eligible(self):
        from workspace.services.crm_match_notifications import is_match_eligible
        self.assertTrue(is_builder_customer(self.builder))
        self.assertTrue(is_match_eligible(self.builder))

    def test_builder_dual_match_groups(self):
        data = get_builder_customer_matches(self.builder, self.user, divar_enabled=False)
        self.assertTrue(data['eligible'])
        self.assertTrue(data['is_builder'])
        self.assertEqual(len(data['match_groups']), 2)
        acquisition = data['match_groups'][0]
        supply = data['match_groups'][1]
        self.assertEqual(acquisition['id'], 'acquisition')
        self.assertEqual(supply['id'], 'supply')
        acq_titles = [m['title'] for m in acquisition['crm_matches']]
        supply_titles = [m['title'] for m in supply['crm_matches']]
        self.assertIn(self.land.title, acq_titles)
        self.assertIn(self.apartment.title, supply_titles)

    def test_get_customer_matches_routes_builder(self):
        data = get_customer_matches(self.builder, self.user, divar_enabled=False)
        self.assertTrue(data['is_builder'])
        self.assertTrue(data['match_groups'])
