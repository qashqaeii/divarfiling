"""تطبیق SQL پیش‌فیلتر با ارزیابی Python — کاندیدای واجد شرایط قطعی حذف نشود."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching import (
    _crm_match_candidates_qs,
    _profile_criteria_eligible,
    match_crm_properties,
)

User = get_user_model()


class MatchingSqlPrefilterAreaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121112222', phone='09121112222', password='x')
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار متراژ',
            phone='09121112222',
            customer_type='خریدار',
            budget_min=8_000_000_000,
            budget_max=20_000_000_000,
            min_area=80,
            max_area=120,
            areas='ونک',
            matching_tolerance_percent=20,
        )

    def _eligible(self, prop: CRMProperty) -> bool:
        return _profile_criteria_eligible(
            self.buyer,
            area=prop.area,
            prop_type=prop.property_type,
            neighborhood=prop.neighborhood or '',
            city=prop.city or '',
            district=prop.district or '',
            rooms=prop.rooms,
            sale_price=prop.sale_price,
            is_rent=False,
        )

    def test_area_none_still_in_sql_candidates_when_python_eligible(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='بدون متراژ',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=None,
            rooms='2',
        )
        self.assertTrue(self._eligible(prop))
        candidate_ids = set(
            _crm_match_candidates_qs(self.buyer, self.user, scan_limit=50).values_list('pk', flat=True)
        )
        self.assertIn(prop.pk, candidate_ids)

    def test_match_crm_properties_includes_area_none_property(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک بدون متراژ در نتایج',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=10_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=None,
            rooms='2',
        )
        matches = match_crm_properties(self.buyer, self.user)
        ids = {m['property_id'] for m in matches}
        self.assertIn(prop.pk, ids)


class MatchingSqlPrefilterRentUnknownTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123334444', phone='09123334444', password='x')
        self.tenant = Customer.objects.create(
            user=self.user,
            name='مستاجر',
            phone='09123334444',
            customer_type='مستاجر',
            deposit_min=200_000_000,
            deposit_max=400_000_000,
            rent_min=10_000_000,
            rent_max=20_000_000,
            areas='ونک',
            matching_tolerance_percent=20,
        )

    def test_rent_unknown_with_deposit_in_candidates(self):
        prop = CRMProperty.objects.create(
            user=self.user,
            title='رهن بدون اجاره',
            property_type='آپارتمان',
            deal_mode='رهن و اجاره',
            transaction_status='فعال',
            deposit=300_000_000,
            monthly_rent=None,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )
        candidate_ids = set(
            _crm_match_candidates_qs(self.tenant, self.user, scan_limit=50).values_list('pk', flat=True)
        )
        self.assertIn(prop.pk, candidate_ids)
