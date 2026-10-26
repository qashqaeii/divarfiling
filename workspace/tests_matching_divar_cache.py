"""رگرسیون کش و hydrate آگهی‌های دیوار در تطبیق."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from workspace.models import Customer, Dataset, Listing
from workspace.services.advertiser_signal import ADVERTISER_SIGNAL_GENUINE_PERSONAL
from workspace.services.crm_matching import get_customer_matches
from workspace.services.crm_matching_index import (
    ScoredRef,
    build_divar_index,
    hydrate_divar_matches,
    user_divar_listings_catalog_extra,
)

User = get_user_model()


@override_settings(CACHES={
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
})
class DivarMatchCacheRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='09128887777', phone='09128887777', password='x',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='match-cache-ds',
            original_filename='t.xlsx',
            file_format='xlsx',
            is_active=True,
        )
        self.buyer = Customer.objects.create(
            user=self.user,
            name='خریدار',
            phone='09128880001',
            customer_type='خریدار',
            budget_min=10_000_000_000,
            budget_max=20_000_000_000,
            areas='ونک',
            property_type='آپارتمان',
            matching_tolerance_percent=20,
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='divar-price-1',
            title='آپارتمان ونک',
            business_type='شخصی',
            advertiser_signal=ADVERTISER_SIGNAL_GENUINE_PERSONAL,
            price=25_000_000_000,
            neighborhood='ونک',
            city='تهران',
            area=90,
            is_expired=False,
        )

    def test_catalog_extra_changes_when_listing_price_changes(self):
        before = user_divar_listings_catalog_extra(self.user)
        self.listing.price = 15_000_000_000
        self.listing.save(update_fields=['price'])
        after = user_divar_listings_catalog_extra(self.user)
        self.assertNotEqual(before, after)

    def test_newly_eligible_listing_after_price_drop_without_manual_rebuild(self):
        cache.clear()
        out_high = get_customer_matches(
            self.buyer, self.user, divar_enabled=True,
            crm_page=1, divar_page=1, page_size=24,
            rebuild_index=True,
        )
        tokens_high = {m['token'] for m in out_high['divar_matches']}
        self.assertNotIn(self.listing.token, tokens_high)

        self.listing.price = 15_000_000_000
        self.listing.save(update_fields=['price'])

        out_low = get_customer_matches(
            self.buyer, self.user, divar_enabled=True,
            crm_page=1, divar_page=1, page_size=24,
            rebuild_index=False,
        )
        tokens_low = {m['token'] for m in out_low['divar_matches']}
        self.assertIn(self.listing.token, tokens_low)

    def test_hydrate_drops_listing_when_no_longer_genuine_owner(self):
        refs = build_divar_index(self.buyer, self.user, min_score=25)
        ref = next((r for r in refs if r.item_id == self.listing.pk), None)
        if ref is None:
            self.listing.price = 15_000_000_000
            self.listing.save(update_fields=['price'])
            refs = build_divar_index(self.buyer, self.user, min_score=25)
            ref = next(r for r in refs if r.item_id == self.listing.pk)

        hydrated = hydrate_divar_matches(
            self.buyer, self.user, [ref], min_score=25,
        )
        self.assertEqual(len(hydrated), 1)

        self.listing.business_type = 'مشاور املاک'
        self.listing.description = 'مشاور رسمی املاک با کد صنفی'
        self.listing.save(update_fields=['business_type', 'description'])

        stale_ref = ScoredRef(ref.score, self.listing.pk)
        hydrated_after = hydrate_divar_matches(
            self.buyer, self.user, [stale_ref], min_score=25,
        )
        self.assertEqual(hydrated_after, [])

    def test_catalog_extra_is_revision_only_no_listing_sql(self):
        with CaptureQueriesContext(connection) as ctx:
            user_divar_listings_catalog_extra(self.user)
        self.assertEqual(len(ctx.captured_queries), 0)

    def test_cache_hit_avoids_listing_table_scan(self):
        get_customer_matches(
            self.buyer, self.user, divar_enabled=True,
            crm_page=1, divar_page=1, page_size=24,
            rebuild_index=True,
        )
        with CaptureQueriesContext(connection) as captured:
            get_customer_matches(
                self.buyer, self.user, divar_enabled=True,
                crm_page=1, divar_page=1, page_size=24,
                rebuild_index=False,
            )
        sql_blob = ' '.join(q['sql'].lower() for q in captured.captured_queries)
        self.assertNotIn('sum(', sql_blob)
        self.assertLessEqual(sql_blob.count('from "workspace_listing"'), 1)
        self._last_cache_hit_query_count = len(captured.captured_queries)
