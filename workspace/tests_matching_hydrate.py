"""رگرسیون hydrate — اعتبارسنجی وضعیت جاری."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching_index import (
    ScoredRef,
    build_crm_index,
    hydrate_crm_matches,
    hydrate_divar_matches,
)

User = get_user_model()


class CrmHydrateValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125554444', phone='09125554444', password='x')
        self.customer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09125550001',
            customer_type='خریدار',
            budget_min=1_000_000_000,
            budget_max=3_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
        )
        self.prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک فعال',
            property_type='آپارتمان',
            deal_mode='فروش',
            transaction_status='فعال',
            sale_price=2_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
        )

    def test_hydrate_excludes_archived_property_from_stale_index_ref(self):
        refs = build_crm_index(self.customer, self.user, min_score=25)
        ref = next((r for r in refs if r.item_id == self.prop.pk), None)
        self.assertIsNotNone(ref)
        self.prop.archived_at = timezone.now()
        self.prop.save(update_fields=['archived_at', 'updated_at'])
        out = hydrate_crm_matches(self.customer, self.user, [ref], min_score=25)
        self.assertEqual(out, [])


class BuilderDivarHydrateValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124443322', phone='09124443322', password='x')
        self.dataset = Dataset.objects.create(
            user=self.user, name='ds', original_filename='a.xlsx', file_format='xlsx', is_active=True,
        )
        self.builder = Customer.objects.create(
            user=self.user,
            name='سازنده',
            phone='09124440001',
            customer_type='سازنده',
            builder_buy_property_types='آپارتمان',
            builder_buy_budget_min=5_000_000_000,
            builder_buy_budget_max=50_000_000_000,
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='bldr-1',
            title='آپارتمان',
            business_type='شخصی',
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=10_000_000_000,
            area=100,
            is_expired=False,
        )

    def test_hydrate_drops_expired_listing_with_stale_ref(self):
        from workspace.services.crm_matching import (
            _builder_acquisition_profile,
            BUILDER_MATCH_INTENTS,
        )

        profile = _builder_acquisition_profile(self.builder)
        meta = BUILDER_MATCH_INTENTS['acquisition']
        ref = ScoredRef(80, self.listing.pk)
        ok = hydrate_divar_matches(
            self.builder, self.user, [ref], min_score=25,
            profile=profile,
            match_intent='acquisition',
            intent_label=meta['intent_label'],
        )
        self.assertEqual(len(ok), 1)
        self.listing.is_expired = True
        self.listing.save(update_fields=['is_expired'])
        stale = hydrate_divar_matches(
            self.builder, self.user, [ref], min_score=25,
            profile=profile,
            match_intent='acquisition',
            intent_label=meta['intent_label'],
        )
        self.assertEqual(stale, [])
