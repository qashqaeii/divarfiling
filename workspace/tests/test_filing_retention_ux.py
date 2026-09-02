"""تست UX و منطق retention مبتنی بر inactivity و پاک‌سازی ماهانه."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from workspace.constants import FILING_LISTING_RETENTION_DAYS_DEFAULT
from workspace.models import Dataset, Listing
from workspace.services.filing_retention import purge_stale_filing_listings
from workspace.services.listing_activity import touch_listing_activity
from workspace.services.listing_retention_calendar import (
    first_cleanup_on_or_after,
    scheduled_deletion_at,
)
from workspace.services.listing_retention_status import (
    RETENTION_STATUS_NORMAL,
    RETENTION_STATUS_WARNING,
    retention_info_for_listing,
)

User = get_user_model()
RETENTION_DAYS = FILING_LISTING_RETENTION_DAYS_DEFAULT


class RetentionInactivityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09140000001', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='inact', is_active=True)

    def test_new_listing_no_warning(self):
        listing = Listing.objects.create(dataset=self.dataset, token='new-1', title='x')
        info = retention_info_for_listing(listing)
        self.assertEqual(info['status'], RETENTION_STATUS_NORMAL)

    def test_old_divar_published_at_does_not_make_warning_if_recent_filing(self):
        listing = Listing.objects.create(dataset=self.dataset, token='pub-1', title='x')
        old_pub = timezone.now() - timedelta(days=120)
        Listing.objects.filter(pk=listing.pk).update(
            created_at=timezone.now() - timedelta(days=5),
            published_at=old_pub,
        )
        listing.refresh_from_db()
        info = retention_info_for_listing(listing)
        self.assertEqual(info['status'], RETENTION_STATUS_NORMAL)

    def test_activity_resets_inactivity_clock(self):
        listing = Listing.objects.create(dataset=self.dataset, token='act-1', title='x')
        old = timezone.now() - timedelta(days=RETENTION_DAYS + 10)
        Listing.objects.filter(pk=listing.pk).update(created_at=old, published_at=old)
        listing.refresh_from_db()
        touch_listing_activity(self.user, listing.token, at=timezone.now() - timedelta(days=5))
        info = retention_info_for_listing(listing)
        self.assertEqual(info['status'], RETENTION_STATUS_NORMAL)

    def test_scheduled_deletion_is_first_monthly_cleanup_after_threshold(self):
        effective = timezone.now() - timedelta(days=RETENTION_DAYS + 1)
        scheduled = scheduled_deletion_at(effective, retention_days=RETENTION_DAYS)
        self.assertIsNotNone(scheduled)
        self.assertEqual(
            scheduled,
            first_cleanup_on_or_after(effective + timedelta(days=RETENTION_DAYS)),
        )

    @patch('workspace.services.listing_retention_status.timezone.now')
    def test_warning_status_three_days_before_cleanup(self, mock_now):
        tz = timezone.get_current_timezone()
        effective = timezone.datetime(2026, 6, 20, 12, 0, tzinfo=tz)
        threshold = effective + timedelta(days=RETENTION_DAYS)
        scheduled = scheduled_deletion_at(effective, retention_days=RETENTION_DAYS, as_of=threshold)
        self.assertIsNotNone(scheduled)
        mock_now.return_value = scheduled - timedelta(days=3)
        listing = Listing.objects.create(dataset=self.dataset, token='warn-1', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=effective, published_at=effective)
        listing.refresh_from_db()
        info = retention_info_for_listing(listing, as_of=mock_now.return_value)
        self.assertEqual(info['status'], RETENTION_STATUS_WARNING)
        self.assertEqual(info.get('days_remaining'), 3)


class RetentionMonthlyPurgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09140000002', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='purge', is_active=True)

    def _stale_listing(self, token: str):
        listing = Listing.objects.create(dataset=self.dataset, token=token, title='x')
        old = timezone.now() - timedelta(days=RETENTION_DAYS + 5)
        Listing.objects.filter(pk=listing.pk).update(created_at=old, published_at=old)
        return listing

    @patch('workspace.services.filing_retention.is_monthly_cleanup_day', return_value=False)
    def test_purge_skipped_outside_cleanup_day(self, _mock_day):
        self._stale_listing('skip-day')
        with override_settings(FILING_LISTING_RETENTION_DAYS=RETENTION_DAYS):
            stats = purge_stale_filing_listings(dry_run=False)
        self.assertEqual(stats['deleted'], 0)
        self.assertTrue(Listing.objects.filter(token='skip-day').exists())

    @patch('workspace.services.filing_retention.is_monthly_cleanup_day', return_value=True)
    def test_purge_runs_on_cleanup_day(self, _mock_day):
        self._stale_listing('purge-me')
        with override_settings(FILING_LISTING_RETENTION_DAYS=RETENTION_DAYS):
            stats = purge_stale_filing_listings(dry_run=False, force_schedule=True)
        self.assertGreaterEqual(stats['deleted'], 1)
        self.assertFalse(Listing.objects.filter(token='purge-me').exists())

    @patch('workspace.services.listing_retention_status.timezone.now')
    def test_activity_in_warning_window_resets_status(self, mock_now):
        tz = timezone.get_current_timezone()
        effective = timezone.datetime(2026, 6, 20, 12, 0, tzinfo=tz)
        scheduled = scheduled_deletion_at(effective, retention_days=RETENTION_DAYS, as_of=effective + timedelta(days=RETENTION_DAYS))
        mock_now.return_value = scheduled - timedelta(days=2)
        listing = Listing.objects.create(dataset=self.dataset, token='reset-warn', title='x')
        Listing.objects.filter(pk=listing.pk).update(created_at=effective, published_at=effective)
        listing.refresh_from_db()
        info = retention_info_for_listing(listing, as_of=mock_now.return_value)
        self.assertEqual(info['status'], RETENTION_STATUS_WARNING)
        touch_listing_activity(self.user, listing.token, at=mock_now.return_value)
        info2 = retention_info_for_listing(listing, as_of=mock_now.return_value)
        self.assertEqual(info2['status'], RETENTION_STATUS_NORMAL)


class RetentionNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09140000003', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='notify', is_active=True)

    @patch('workspace.services.filing_retention_notifications._warning_window_active', return_value=True)
    @patch('workspace.services.filing_retention_notifications.count_warning_listings_for_user', return_value=3)
    def test_notification_dedup_per_cycle(self, _count, _window):
        from mobile_api.models import MobileNotification
        from workspace.services.filing_retention_notifications import notify_filing_retention_warnings

        stats1 = notify_filing_retention_warnings(dry_run=False)
        stats2 = notify_filing_retention_warnings(dry_run=False)
        self.assertEqual(stats1['notifications_created'], 1)
        self.assertEqual(stats2['notifications_created'], 0)
        self.assertEqual(
            MobileNotification.objects.filter(user=self.user, notification_type='filing_retention_warning').count(),
            1,
        )


class RetentionRolloutSafetyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09140000004', password='x')
        self.dataset = Dataset.objects.create(user=self.user, name='rollout', is_active=True)

    @patch('workspace.services.filing_retention.is_monthly_cleanup_day', return_value=True)
    def test_first_deploy_blocks_purge_without_full_warning_window(self, _mock_day):
        tz = timezone.get_current_timezone()
        deploy_at = timezone.datetime(2026, 9, 28, 10, 0, tzinfo=tz)
        listing = Listing.objects.create(dataset=self.dataset, token='rollout-1', title='x')
        old = deploy_at - timedelta(days=RETENTION_DAYS + 30)
        Listing.objects.filter(pk=listing.pk).update(created_at=old, published_at=old)
        with override_settings(
            FILING_LISTING_RETENTION_DAYS=RETENTION_DAYS,
            RETENTION_WARNING_FEATURE_DEPLOYED_AT=deploy_at.isoformat(),
        ):
            with patch('workspace.services.listing_retention_status.timezone.now', return_value=deploy_at + timedelta(days=1)):
                stats = purge_stale_filing_listings(dry_run=False, force_schedule=True)
        self.assertEqual(stats['deleted'], 0)
        self.assertTrue(Listing.objects.filter(token='rollout-1').exists())


class RetentionCrossUserIsolationTests(TestCase):
    def test_activity_does_not_leak_between_users(self):
        user_a = User.objects.create_user(username='ux-a', password='x', phone='09143333331')
        user_b = User.objects.create_user(username='ux-b', password='x', phone='09143333332')
        ds_a = Dataset.objects.create(user=user_a, name='a', is_active=True)
        ds_b = Dataset.objects.create(user=user_b, name='b', is_active=True)
        old = timezone.now() - timedelta(days=RETENTION_DAYS + 10)
        la = Listing.objects.create(dataset=ds_a, token='shared-tok', title='a')
        lb = Listing.objects.create(dataset=ds_b, token='shared-tok', title='b')
        Listing.objects.filter(pk__in=[la.pk, lb.pk]).update(created_at=old, published_at=old)
        touch_listing_activity(user_a, 'shared-tok', at=timezone.now())
        info_a = retention_info_for_listing(la)
        info_b = retention_info_for_listing(lb)
        self.assertEqual(info_a['status'], RETENTION_STATUS_NORMAL)
        self.assertLess(
            info_b['last_activity_at'],
            info_a['last_activity_at'],
        )
