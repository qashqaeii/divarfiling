"""Regression tests for listing public share FK/race handling."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import Dataset, Listing, ListingPublicShare
from workspace.services.listing_public_share import (
    get_listing_share,
    get_or_create_listing_share,
    listing_share_for_display,
)

User = get_user_model()


class ListingShareIntegrityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09123334455',
            phone='09123334455',
            password='testpass123',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='test.xlsx',
            file_format='xlsx',
            transaction_type='فروش',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='share-test',
            title='ملک تست',
            price=1_000_000_000,
            area=100,
        )
        self.client = Client()
        self.client.force_login(self.user)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_get_listing_share_read_only(self, _license):
        self.assertIsNone(get_listing_share(self.user, self.listing))
        created = get_or_create_listing_share(self.user, self.listing)
        self.assertIsNotNone(created)
        self.assertEqual(get_listing_share(self.user, self.listing).pk, created.pk)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_get_or_create_after_listing_delete_returns_none(self, _license):
        listing_id = self.listing.pk
        self.listing.delete()
        ghost = Listing(pk=listing_id, dataset=self.dataset, token='ghost')
        self.assertIsNone(get_or_create_listing_share(self.user, ghost))

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_detail_get_does_not_create_share(self, _license):
        url = reverse(
            'workspace:listing_detail',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ListingPublicShare.objects.count(), 0)

    @patch('workspace.mixins.has_active_bot_license', return_value=True)
    def test_listing_share_manage_get_creates_share(self, _license):
        url = reverse(
            'workspace:listing_share',
            kwargs={'dataset_id': self.dataset.pk, 'listing_id': self.listing.pk},
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(ListingPublicShare.objects.count(), 1)

    def test_listing_share_for_display_uses_stub_without_db_row(self):
        display = listing_share_for_display(self.user, self.listing)
        self.assertFalse(getattr(display, 'share_token', ''))
