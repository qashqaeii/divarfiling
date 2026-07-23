"""تست فیلتر مالک واقعی در پیشنهادهای فایلینگ دیوار."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from workspace.models import Customer, Dataset, Listing
from workspace.services.advertiser_signal import (
    ADVERTISER_SIGNAL_DISGUISED,
    ADVERTISER_SIGNAL_GENUINE_PERSONAL,
)
from workspace.services.crm_matching import get_customer_matches, match_divar_listings

User = get_user_model()


class DivarGenuineOwnerMatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09127778888', phone='09127778888', password='x',
        )
        self.dataset = Dataset.objects.create(
            user=self.user, name='تست تطبیق', is_active=True,
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار مالک',
            phone='09127778888',
            customer_type='خریدار',
            budget_min=1_000_000_000,
            budget_max=20_000_000_000,
            min_area=50,
            max_area=200,
            areas='ونک',
        )
        self.genuine = Listing.objects.create(
            dataset=self.dataset,
            token='gen-own-1',
            title='آپارتمان ونک مالک هستم',
            description='فروشنده مالک هستم، بدون واسطه',
            business_type='شخصی',
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=8_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            rooms='2',
            is_expired=False,
        )
        self.disguised = Listing.objects.create(
            dataset=self.dataset,
            token='disg-1',
            title='آپارتمان ونک فایل شخصی مشاور منطقه',
            description='مشاور املاک منطقه ونک، گروه مشاورین املاک',
            business_type='شخصی',
            advertiser_signal=ADVERTISER_SIGNAL_DISGUISED,
            price=8_500_000_000,
            neighborhood='ونک',
            city='تهران',
            area=95,
            rooms='2',
            is_expired=False,
        )
        self.consultant = Listing.objects.create(
            dataset=self.dataset,
            token='cons-1',
            title='آپارتمان ونک آژانس',
            description='آژانس املاک',
            business_type='مشاور',
            advertiser_signal='consultant',
            price=7_500_000_000,
            neighborhood='ونک',
            city='تهران',
            area=85,
            rooms='2',
            is_expired=False,
        )

    def test_divar_matches_only_genuine_owner(self):
        matches = match_divar_listings(self.buyer, self.user)
        tokens = [m['token'] for m in matches]
        self.assertIn(self.genuine.token, tokens)
        self.assertNotIn(self.disguised.token, tokens)
        self.assertNotIn(self.consultant.token, tokens)

    def test_get_customer_matches_excludes_disguised(self):
        data = get_customer_matches(self.buyer, self.user, divar_enabled=True)
        tokens = [m['token'] for m in data['divar_matches']]
        self.assertIn(self.genuine.token, tokens)
        self.assertNotIn(self.disguised.token, tokens)
        self.assertNotIn(self.consultant.token, tokens)
