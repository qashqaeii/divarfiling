"""تست سرکوب آگهی، lifecycle دیتاست، و retention فایلینگ."""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from mobile_api.services.extraction_ingest import ingest_mobile_extraction
from workspace.models import CRMProperty, Dataset, Listing, UserListingSuppression
from workspace.services.crm import add_listing_to_personal_files
from workspace.services.filing_delete import delete_divar_listing_from_filing
from workspace.services.filing_retention import purge_stale_filing_listings
from workspace.services.importer import import_dataset
from workspace.services.ingest_mode import INGEST_MODE_INCREMENTAL, INGEST_MODE_SNAPSHOT
from workspace.services.listing_personal_status import DIVAR_SOURCE_PLATFORM
from workspace.services.listing_suppression import is_suppressed
from workspace.views import _soft_delete_datasets

User = get_user_model()


def _rent_detail(token: str) -> dict:
    return {
        'seo': {'web_info': {'title': 'اجاره آپارتمان', 'city_persian': 'تهران'}},
        'share': {'web_url': f'https://divar.ir/v/{token}'},
        'webengage': {'token': token, 'business_type': 'personal'},
        'sections': [
            {
                'section_name': 'LIST_DATA',
                'widgets': [
                    {
                        'widget_type': 'RENT_SLIDER',
                        'data': {
                            'credit': {'value': '۵۰۰٬۰۰۰٬۰۰۰ تومان'},
                            'rent': {'value': '۱۵٬۰۰۰٬۰۰۰ تومان'},
                        },
                    },
                ],
            },
        ],
    }


def _mobile_payload(token: str, *, hint: str = 'ostad-moein') -> dict:
    return {
        'filters': {
            'category': 'apartment-rent',
            'category_label': 'آپارتمان',
            'transaction_type_label': 'اجاره مسکونی',
            'city_name': 'تهران',
            'district_names': ['استاد معین'],
            'output_name_hint': hint,
            'max_items': 1,
        },
        'started_at': timezone.now().isoformat(),
        'finished_at': timezone.now().isoformat(),
        'items': [{'token': token, 'raw': _rent_detail(token)}],
    }


class ListingSuppressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121110001', password='x', phone='09121110001')
        self.other = User.objects.create_user(username='09121110002', password='x', phone='09121110002')

    def _ingest(self, user, token: str, hint: str = 'sup-test'):
        return ingest_mobile_extraction(user, _mobile_payload(token, hint=hint))

    def test_delete_then_reextract_skips_token(self):
        self._ingest(self.user, 'tok-x')
        delete_divar_listing_from_filing(self.user, 'tok-x')
        self.assertTrue(is_suppressed(self.user, DIVAR_SOURCE_PLATFORM, 'tok-x'))
        result = self._ingest(self.user, 'tok-x', hint='sup-test-2')
        self.assertEqual(result.suppressed_count, 1)
        self.assertFalse(Listing.objects.filter(dataset__user=self.user, token='tok-x').exists())

    def test_delete_removes_all_copies_once(self):
        ds1 = Dataset.objects.create(user=self.user, name='a')
        ds2 = Dataset.objects.create(user=self.user, name='b')
        Listing.objects.create(dataset=ds1, token='multi-x', title='a')
        Listing.objects.create(dataset=ds2, token='multi-x', title='b')
        delete_divar_listing_from_filing(self.user, 'multi-x')
        self.assertEqual(Listing.objects.filter(dataset__user=self.user, token='multi-x').count(), 0)
        self.assertEqual(
            UserListingSuppression.objects.filter(
                user=self.user, source_platform=DIVAR_SOURCE_PLATFORM, external_id='multi-x',
            ).count(),
            1,
        )

    def test_other_user_still_receives_token(self):
        delete_divar_listing_from_filing(self.user, 'shared-tok')
        result = self._ingest(self.other, 'shared-tok', hint='other-file')
        self.assertEqual(result.created_count, 1)
        self.assertTrue(Listing.objects.filter(dataset__user=self.other, token='shared-tok').exists())

    def test_mobile_api_delete_suppresses(self):
        self._ingest(self.user, 'api-del')
        client = APIClient()
        client.force_authenticate(user=self.user)
        with patch('mobile_api.services.filing_service.has_active_bot_license', return_value=True):
            resp = client.delete('/api/mobile/v1/filing/listings/api-del')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(is_suppressed(self.user, DIVAR_SOURCE_PLATFORM, 'api-del'))
        result = self._ingest(self.user, 'api-del', hint='after-api-del')
        self.assertEqual(result.suppressed_count, 1)

    def test_windows_import_skips_suppressed(self):
        delete_divar_listing_from_filing(self.user, 'win-tok')
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tmp:
            json.dump([{'token': 'win-tok', 'title': 't'}], tmp, ensure_ascii=False)
            tmp_path = tmp.name
        try:
            rel = 'تهران/استاد_معین/اجاره_آپارتمان/win.json'
            result = import_dataset(self.user, tmp_path, 'win.json', path_info={
                'relative_path': rel,
                'city': 'تهران',
                'district': 'استاد معین',
                'transaction_type': 'اجاره مسکونی',
                'subcategory': 'آپارتمان',
            })
            self.assertEqual(result.suppressed_count, 1)
            self.assertFalse(Listing.objects.filter(dataset__user=self.user, token='win-tok').exists())
        finally:
            os.unlink(tmp_path)

    def test_cloud_ingest_skips_suppressed(self):
        delete_divar_listing_from_filing(self.user, 'cloud-tok')
        payload = _mobile_payload('cloud-tok', hint='cloud')
        payload['filters']['source_client'] = 'cloud_extract'
        result = ingest_mobile_extraction(self.user, payload)
        self.assertEqual(result.suppressed_count, 1)
        self.assertFalse(Listing.objects.filter(dataset__user=self.user, token='cloud-tok').exists())


class CRMSafetyWithSuppressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09122220001', password='x')

    def test_crm_property_survives_filing_delete(self):
        ds = Dataset.objects.create(user=self.user, name='f')
        listing = Listing.objects.create(dataset=ds, token='crm-keep', title='ملک')
        prop, _ = add_listing_to_personal_files(self.user, listing)
        delete_divar_listing_from_filing(self.user, 'crm-keep')
        prop.refresh_from_db()
        self.assertIsNone(prop.deleted_at)
        self.assertTrue(CRMProperty.objects.filter(pk=prop.pk).exists())

    def test_dataset_delete_does_not_create_suppression(self):
        result = ingest_mobile_extraction(self.user, _mobile_payload('ds-del-tok'))
        ds = result.dataset
        _soft_delete_datasets(Dataset.objects.filter(pk=ds.pk))
        self.assertFalse(
            UserListingSuppression.objects.filter(user=self.user, external_id='ds-del-tok').exists(),
        )

    def test_retention_does_not_create_suppression(self):
        ds = Dataset.objects.create(user=self.user, name='old')
        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=ds, token='old-tok', title='قدیمی')
        Listing.objects.filter(pk=listing.pk).update(created_at=old, published_at=None)
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            stats = purge_stale_filing_listings(dry_run=False)
        self.assertGreaterEqual(stats['deleted'], 1)
        self.assertFalse(
            UserListingSuppression.objects.filter(user=self.user, external_id='old-tok').exists(),
        )
        self.assertFalse(Listing.objects.filter(token='old-tok').exists())


class DatasetLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09123330001', password='x')

    def test_deleted_dataset_not_reactivated_on_reimport(self):
        first = ingest_mobile_extraction(self.user, _mobile_payload('life-a', hint='life-hint'))
        old_id = first.dataset.pk
        _soft_delete_datasets(Dataset.objects.filter(pk=old_id))
        old = Dataset.objects.get(pk=old_id)
        self.assertFalse(old.is_active)
        second = ingest_mobile_extraction(self.user, _mobile_payload('life-b', hint='life-hint'))
        self.assertNotEqual(second.dataset.pk, old_id)
        self.assertTrue(second.dataset.is_active)
        old.refresh_from_db()
        self.assertFalse(old.is_active)

    def test_new_dataset_only_incoming_records(self):
        first = ingest_mobile_extraction(self.user, _mobile_payload('hist-a', hint='hist-hint'))
        _soft_delete_datasets(Dataset.objects.filter(pk=first.dataset.pk))
        second = ingest_mobile_extraction(self.user, _mobile_payload('hist-d', hint='hist-hint'))
        tokens = set(second.dataset.listings.values_list('token', flat=True))
        self.assertEqual(tokens, {'hist-d'})
        self.assertNotIn('hist-a', tokens)

    def test_suppressed_token_excluded_from_new_dataset(self):
        delete_divar_listing_from_filing(self.user, 'sup-c')
        first = ingest_mobile_extraction(self.user, _mobile_payload('hist-d', hint='mix-hint'))
        _soft_delete_datasets(Dataset.objects.filter(pk=first.dataset.pk))
        payload = _mobile_payload('sup-c', hint='mix-hint')
        payload['items'].append({'token': 'hist-e', 'raw': _rent_detail('hist-e')})
        payload['filters']['max_items'] = 2
        second = ingest_mobile_extraction(self.user, payload)
        tokens = set(second.dataset.listings.values_list('token', flat=True))
        self.assertEqual(tokens, {'hist-e'})


class PersonalizeDoesNotSuppressTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124440001', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='f')
        self.listing = Listing.objects.create(
            dataset=self.dataset, token='pers-tok', title='آپارتمان',
        )

    def test_personalize_does_not_create_suppression(self):
        add_listing_to_personal_files(self.user, self.listing)
        self.assertFalse(
            UserListingSuppression.objects.filter(user=self.user, external_id='pers-tok').exists(),
        )

    def test_reextract_after_personalize_allowed_if_not_user_deleted(self):
        add_listing_to_personal_files(self.user, self.listing)
        result = ingest_mobile_extraction(self.user, _mobile_payload('pers-tok', hint='pers-re'))
        self.assertEqual(result.created_count, 1)
        self.assertTrue(Listing.objects.filter(dataset__user=self.user, token='pers-tok').exists())


class RetentionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09125550001', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='ret', is_active=True)

    def test_stale_listing_purged_fresh_kept(self):
        old = timezone.now() - timezone.timedelta(days=40)
        fresh = timezone.now() - timezone.timedelta(days=5)
        stale = Listing.objects.create(dataset=self.dataset, token='stale-1', title='قدیمی')
        keep = Listing.objects.create(dataset=self.dataset, token='fresh-1', title='تازه')
        Listing.objects.filter(pk=stale.pk).update(created_at=old, published_at=None)
        Listing.objects.filter(pk=keep.pk).update(created_at=fresh, published_at=fresh)
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            stats = purge_stale_filing_listings(dry_run=False)
        self.assertGreaterEqual(stats['deleted'], 1)
        self.assertFalse(Listing.objects.filter(token='stale-1').exists())
        self.assertTrue(Listing.objects.filter(token='fresh-1').exists())

    def test_dry_run_makes_no_changes(self):
        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=self.dataset, token='dry-1', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=old)
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            stats = purge_stale_filing_listings(dry_run=True)
        self.assertGreaterEqual(stats['eligible'], 1)
        self.assertEqual(stats['deleted'], 0)
        self.assertTrue(Listing.objects.filter(token='dry-1').exists())

    def test_retention_syncs_row_count(self):
        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=self.dataset, token='sync-1', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=old)
        self.dataset.row_count = 1
        self.dataset.save(update_fields=['row_count'])
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            purge_stale_filing_listings(dry_run=False)
        self.dataset.refresh_from_db()
        self.assertEqual(self.dataset.row_count, 0)


class IngestModeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09126660001', password='x')

    def test_mobile_uses_incremental_no_prune(self):
        filters = {
            'category': 'apartment-rent',
            'category_label': 'آپارتمان',
            'transaction_type_label': 'اجاره مسکونی',
            'city_name': 'تهران',
            'district_names': ['استاد معین'],
            'output_name_hint': 'incr-hint',
            'max_items': 1,
        }
        first = ingest_mobile_extraction(self.user, {
            'filters': filters,
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'incr-a', 'raw': _rent_detail('incr-a')}],
        })
        second = ingest_mobile_extraction(self.user, {
            'filters': filters,
            'started_at': timezone.now().isoformat(),
            'finished_at': timezone.now().isoformat(),
            'items': [{'token': 'incr-b', 'raw': _rent_detail('incr-b')}],
        })
        self.assertEqual(first.dataset.pk, second.dataset.pk)
        self.assertEqual(second.dataset.listings.count(), 2)
        self.assertEqual(
            (second.dataset.metadata or {}).get('ingest_mode'),
            INGEST_MODE_INCREMENTAL,
        )

    def test_windows_folder_import_snapshot_prunes(self):
        rel = 'تهران/استاد_معین/اجاره_آپارتمان/snap.json'
        path_info = {
            'relative_path': rel,
            'city': 'تهران',
            'district': 'استاد معین',
            'transaction_type': 'اجاره مسکونی',
            'subcategory': 'آپارتمان',
        }

        def _import(tokens):
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tmp:
                json.dump([{'token': t, 'title': t} for t in tokens], tmp, ensure_ascii=False)
                tmp_path = tmp.name
            try:
                return import_dataset(self.user, tmp_path, 'snap.json', path_info=path_info)
            finally:
                os.unlink(tmp_path)

        r1 = _import(['snap-a'])
        r2 = _import(['snap-b'])
        self.assertEqual(r1.dataset.pk, r2.dataset.pk)
        self.assertEqual(set(r2.dataset.listings.values_list('token', flat=True)), {'snap-b'})
        self.assertEqual((r2.dataset.metadata or {}).get('ingest_mode'), INGEST_MODE_SNAPSHOT)


class DatasetIdentityCoexistenceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09128880001', password='x')

    def test_inactive_and_new_active_dataset_same_file_identity(self):
        inactive = Dataset.objects.create(
            user=self.user,
            name='قدیمی',
            original_filename='identity.json',
            file_format='json',
            is_active=False,
            metadata={'file_identity': 'tehran/rent_apt'},
        )
        active = Dataset.objects.create(
            user=self.user,
            name='جدید',
            original_filename='identity.json',
            file_format='json',
            is_active=True,
            metadata={'file_identity': 'tehran/rent_apt'},
        )
        self.assertNotEqual(inactive.pk, active.pk)
        self.assertFalse(inactive.is_active)
        self.assertTrue(active.is_active)


class RetentionCascadeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09129990001', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='ret', is_active=True)

    def test_listing_public_share_cascade_on_retention(self):
        from workspace.models import ListingPublicShare

        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=self.dataset, token='share-tok', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=old)
        share = ListingPublicShare.objects.create(
            share_token='abc12345',
            listing=listing,
            created_by=self.user,
        )
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            purge_stale_filing_listings(dry_run=False)
        self.assertFalse(Listing.objects.filter(pk=listing.pk).exists())
        self.assertFalse(ListingPublicShare.objects.filter(pk=share.pk).exists())

    def test_crm_property_survives_retention(self):
        from workspace.models import CRMProperty

        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=self.dataset, token='crm-ret', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=old)
        prop = CRMProperty.objects.create(
            user=self.user,
            title='ملک',
            source_platform='divar',
            source_external_id='crm-ret',
            token='crm-ret',
        )
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            purge_stale_filing_listings(dry_run=False)
        self.assertTrue(CRMProperty.objects.filter(pk=prop.pk).exists())


class DeleteSemanticsTests(TestCase):
    """چهار semantics حذف — بدون مخلوط شدن."""

    def setUp(self):
        self.user = User.objects.create_user(username='09120000001', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='sem', is_active=True)

    def test_explicit_delete_creates_suppression(self):
        listing = Listing.objects.create(dataset=self.dataset, token='sem-del', title='x')
        delete_divar_listing_from_filing(self.user, listing.token)
        self.assertTrue(UserListingSuppression.objects.filter(user=self.user, external_id='sem-del').exists())

    def test_personalize_no_suppression(self):
        listing = Listing.objects.create(dataset=self.dataset, token='sem-pers', title='x')
        add_listing_to_personal_files(self.user, listing)
        self.assertFalse(UserListingSuppression.objects.filter(user=self.user, external_id='sem-pers').exists())

    def test_retention_no_suppression(self):
        old = timezone.now() - timezone.timedelta(days=40)
        listing = Listing.objects.create(dataset=self.dataset, token='sem-ret', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=old)
        with override_settings(FILING_LISTING_RETENTION_DAYS=31):
            purge_stale_filing_listings(dry_run=False)
        self.assertFalse(UserListingSuppression.objects.filter(user=self.user, external_id='sem-ret').exists())

    def test_dataset_delete_no_mass_suppression(self):
        Listing.objects.create(dataset=self.dataset, token='sem-ds-a', title='a')
        Listing.objects.create(dataset=self.dataset, token='sem-ds-b', title='b')
        _soft_delete_datasets(Dataset.objects.filter(pk=self.dataset.pk))
        self.assertEqual(UserListingSuppression.objects.filter(user=self.user).count(), 0)
