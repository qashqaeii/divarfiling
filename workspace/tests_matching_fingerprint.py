"""رگرسیون fingerprint تطبیق."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import CRMProperty, Customer
from workspace.services.crm_matching_index import (
    customer_match_fingerprint,
    property_match_fingerprint,
)

User = get_user_model()


class MatchFingerprintTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126665555', phone='09126665555', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09126660001',
            customer_type='خریدار',
            budget_min=1_000_000_000,
            budget_max=3_000_000_000,
            rooms_min=2,
            rooms_max=4,
            want_parking=False,
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='تست',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=2_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='3',
            floor=5,
            build_year=1400,
            has_parking=False,
        )

    def test_customer_fingerprint_changes_on_rooms_legacy_field(self):
        before = customer_match_fingerprint(self.customer)
        self.customer.rooms = '3'
        self.customer.save(update_fields=['rooms', 'updated_at'])
        after = customer_match_fingerprint(self.customer)
        self.assertNotEqual(before, after)

    def test_customer_fingerprint_changes_on_amenity_preference(self):
        before = customer_match_fingerprint(self.customer)
        self.customer.want_elevator = True
        self.customer.save(update_fields=['want_elevator', 'updated_at'])
        self.assertNotEqual(before, customer_match_fingerprint(self.customer))

    def test_property_fingerprint_changes_on_floor_and_parking(self):
        before = property_match_fingerprint(self.prop)
        self.prop.floor = 12
        self.prop.has_parking = True
        self.prop.save(update_fields=['floor', 'has_parking', 'updated_at'])
        self.assertNotEqual(before, property_match_fingerprint(self.prop))
