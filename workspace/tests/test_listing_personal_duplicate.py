"""Tests for duplicate prevention when re-extracting Divar listings to personal files."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from workspace.models import CRMProperty, Dataset, Listing
from workspace.services.crm import add_listing_to_personal_files
from workspace.services.crm_property_duplicate import duplicate_property
from workspace.services.listing_personal_status import (
    DIVAR_SOURCE_PLATFORM,
    get_crm_property_by_source_identity,
    personal_property_ids_by_tokens,
)

User = get_user_model()


class ListingPersonalDuplicateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121110001', password='test', phone='09121110001',
        )
        self.other = User.objects.create_user(
            username='09121110002', password='test', phone='09121110002',
        )
        self.dataset = Dataset.objects.create(user=self.user, name='فایل امروز')
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='divar-abc-123',
            title='آپارتمان ۱۰۰ متری',
            price=5_000_000_000,
            city='تهران',
            neighborhood='ونک',
        )

    def _reextract_listing(self):
        dataset2 = Dataset.objects.create(user=self.user, name='فایل فردا')
        return Listing.objects.create(
            dataset=dataset2,
            token='divar-abc-123',
            title='آپارتمان ۱۰۰ متری — بروز',
            price=5_200_000_000,
            city='تهران',
            neighborhood='ونک',
        )

    def test_convert_stores_source_identity(self):
        prop, created = add_listing_to_personal_files(self.user, self.listing)
        self.assertTrue(created)
        prop.refresh_from_db()
        self.assertEqual(prop.source_platform, DIVAR_SOURCE_PLATFORM)
        self.assertEqual(prop.source_external_id, 'divar-abc-123')
        self.assertEqual(prop.token, 'divar-abc-123')

    def test_reextracted_listing_marked_personal_in_api(self):
        prop, _ = add_listing_to_personal_files(self.user, self.listing)
        reextracted = self._reextract_listing()

        client = APIClient()
        client.force_authenticate(user=self.user)
        with patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True):
            resp = client.get(f'/api/mobile/v1/filing/listings/{reextracted.token}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['data']
        self.assertTrue(data['is_added_to_personal'])
        self.assertEqual(data['personal_property_id'], prop.pk)

    def test_list_endpoint_includes_personal_status(self):
        prop, _ = add_listing_to_personal_files(self.user, self.listing)
        reextracted = self._reextract_listing()

        client = APIClient()
        client.force_authenticate(user=self.user)
        with patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True):
            resp = client.get(
                f'/api/mobile/v1/filing/datasets/{reextracted.dataset_id}/listings',
            )
        self.assertEqual(resp.status_code, 200)
        row = resp.json()['data'][0]
        self.assertTrue(row['is_added_to_personal'])
        self.assertEqual(row['personal_property_id'], prop.pk)

    def test_different_listing_not_marked(self):
        other_listing = Listing.objects.create(
            dataset=self.dataset,
            token='divar-other-999',
            title='ویلا',
            price=10_000_000_000,
        )
        add_listing_to_personal_files(self.user, self.listing)

        status_map = personal_property_ids_by_tokens(
            self.user, [other_listing.token, self.listing.token],
        )
        self.assertNotIn(other_listing.token, status_map)

    def test_other_user_not_marked(self):
        add_listing_to_personal_files(self.user, self.listing)
        other_dataset = Dataset.objects.create(user=self.other, name='other')
        other_listing = Listing.objects.create(
            dataset=other_dataset,
            token='divar-abc-123',
            title='همان آگهی',
            price=5_000_000_000,
        )
        status_map = personal_property_ids_by_tokens(self.other, [other_listing.token])
        self.assertEqual(status_map, {})

    def test_second_personalize_returns_existing(self):
        prop1, created1 = add_listing_to_personal_files(self.user, self.listing)
        self.assertTrue(created1)
        reextracted = self._reextract_listing()
        prop2, created2 = add_listing_to_personal_files(self.user, reextracted)
        self.assertFalse(created2)
        self.assertEqual(prop1.pk, prop2.pk)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)

    def test_mobile_create_property_already_added(self):
        prop, _ = add_listing_to_personal_files(self.user, self.listing)
        reextracted = self._reextract_listing()

        client = APIClient()
        client.force_authenticate(user=self.user)
        resp = client.post(
            '/api/mobile/v1/crm/properties',
            {
                'title': reextracted.title,
                'token': reextracted.token,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()['data']
        self.assertTrue(data['already_added'])
        self.assertFalse(data['created'])
        self.assertEqual(data['id'], prop.pk)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)

    def test_manual_property_does_not_block_unrelated_listing(self):
        CRMProperty.objects.create(
            user=self.user,
            title='ملک دستی',
            property_type='آپارتمان',
            deal_mode='فروش',
            city='تهران',
            address='خیابان ولیعصر',
            sale_price=3_000_000_000,
        )
        status_map = personal_property_ids_by_tokens(self.user, [self.listing.token])
        self.assertEqual(status_map, {})

    def test_database_constraint_prevents_duplicate_source_property(self):
        CRMProperty.objects.create(
            user=self.user,
            title='اول',
            property_type='آپارتمان',
            deal_mode='فروش',
            source_platform=DIVAR_SOURCE_PLATFORM,
            source_external_id='divar-abc-123',
            token='divar-abc-123',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CRMProperty.objects.create(
                    user=self.user,
                    title='دوم',
                    property_type='آپارتمان',
                    deal_mode='فروش',
                    source_platform=DIVAR_SOURCE_PLATFORM,
                    source_external_id='divar-abc-123',
                    token='divar-abc-123',
                )

    def test_property_copy_clears_source_identity(self):
        prop, _ = add_listing_to_personal_files(self.user, self.listing)
        copy = duplicate_property(self.user, prop.pk)
        self.assertNotEqual(copy.pk, prop.pk)
        self.assertEqual(copy.source_platform, '')
        self.assertEqual(copy.source_external_id, '')

    def test_reextracted_listing_remains_in_filing(self):
        add_listing_to_personal_files(self.user, self.listing)
        reextracted = self._reextract_listing()
        self.assertTrue(
            Listing.objects.filter(dataset__user=self.user, token=reextracted.token).exists(),
        )

    def test_integrity_error_recovery_after_inner_savepoint(self):
        existing = CRMProperty.objects.create(
            user=self.user,
            title='موجود',
            property_type='آپارتمان',
            deal_mode='فروش',
            source_platform=DIVAR_SOURCE_PLATFORM,
            source_external_id='divar-abc-123',
            token='divar-abc-123',
        )

        def _raise_unique(*_args, **_kwargs):
            raise IntegrityError(
                'duplicate key value violates unique constraint '
                '"uniq_crmproperty_user_source_listing"',
            )

        with patch('workspace.services.crm.property_from_listing', side_effect=_raise_unique):
            prop, created = add_listing_to_personal_files(self.user, self.listing)

        self.assertFalse(created)
        self.assertEqual(prop.pk, existing.pk)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)

    def test_identity_lookup_finds_property_outside_scoped_qs(self):
        existing = CRMProperty.objects.create(
            user=self.user,
            title='scoped hidden',
            property_type='آپارتمان',
            deal_mode='فروش',
            source_platform=DIVAR_SOURCE_PLATFORM,
            source_external_id='divar-abc-123',
            token='divar-abc-123',
        )
        found = get_crm_property_by_source_identity(
            self.user, DIVAR_SOURCE_PLATFORM, 'divar-abc-123',
        )
        self.assertEqual(found.pk, existing.pk)

    def test_stale_personal_post_is_idempotent(self):
        from django.test import Client
        from django.urls import reverse

        prop, created = add_listing_to_personal_files(self.user, self.listing)
        self.assertTrue(created)
        reextracted = self._reextract_listing()
        url = reverse(
            'workspace:listing_add_personal',
            kwargs={'dataset_id': reextracted.dataset_id, 'listing_id': reextracted.pk},
        )
        client = Client()
        client.force_login(self.user)
        resp = client.post(url, {'next': '/workspace/'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CRMProperty.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            CRMProperty.objects.filter(user=self.user).first().pk,
            prop.pk,
        )

    def test_unrelated_integrity_error_is_not_swallowed(self):
        def _raise_other(*_args, **_kwargs):
            raise IntegrityError('some_other_constraint')

        with patch('workspace.services.crm.property_from_listing', side_effect=_raise_other):
            with self.assertRaises(IntegrityError):
                add_listing_to_personal_files(self.user, self.listing)
