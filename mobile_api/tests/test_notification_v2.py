"""تست معماری اعلان V2 — welcome، logout، local-delivered، broadcast."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from mobile_api.models import MobileDevice, MobileNotification, MobileNotificationBroadcast
from mobile_api.services.broadcast_service import process_broadcast, queue_broadcast
from mobile_api.services.notification_catalog import sanitize_deep_link
from mobile_api.services.notification_service import create_notification, maybe_create_welcome
from workspace.models import Customer, Reminder

User = get_user_model()


class NotificationCatalogTests(TestCase):
    def test_rejects_unknown_deep_link(self):
        self.assertEqual(
            sanitize_deep_link('https://evil.example/phish', 'announcement'),
            'divarfiling://notifications',
        )

    def test_allows_whitelisted_contact_link(self):
        self.assertEqual(
            sanitize_deep_link('divarfiling://crm/contacts/12/matches', 'customer_match'),
            'divarfiling://crm/contacts/12/matches',
        )


class WelcomeAndLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120001111', password='test', phone='09120001111')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {token.access_token}',
            HTTP_X_DEVICE_ID='logout-device-1',
        )
        MobileDevice.objects.create(
            user=self.user,
            device_id='logout-device-1',
            fcm_token='tok-abc',
            is_active=True,
        )

    def test_welcome_created_once(self):
        with patch('mobile_api.services.notification_service.send_push_to_user', return_value=1):
            maybe_create_welcome(self.user)
            maybe_create_welcome(self.user)
        self.assertEqual(MobileNotification.objects.filter(notification_type='welcome').count(), 1)
        n = MobileNotification.objects.get(notification_type='welcome')
        self.assertEqual(n.deep_link, 'divarfiling://home')

    def test_logout_clears_fcm_token(self):
        resp = self.client.post('/api/mobile/v1/auth/logout', {'refresh': str(RefreshToken.for_user(self.user))}, format='json')
        self.assertEqual(resp.status_code, 200)
        device = MobileDevice.objects.get(device_id='logout-device-1')
        self.assertEqual(device.fcm_token, '')
        self.assertFalse(device.is_active)


class LocalDeliveredTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120002222', password='test', phone='09120002222')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.customer = Customer.objects.create(user=self.user, name='رضا', phone='09120002222')
        self.reminder = Reminder.objects.create(
            user=self.user,
            customer=self.customer,
            title='تماس تست',
            due_at=timezone.now() + timedelta(hours=1),
        )

    def test_local_delivered_creates_inbox_without_push(self):
        with patch('mobile_api.services.push_service.send_push_to_tokens', return_value={'attempted': 0, 'success': 0, 'failure': 0}):
            resp = self.client.post(
                '/api/mobile/v1/notifications/local-delivered',
                {'reminder_id': self.reminder.pk},
                format='json',
            )
        self.assertEqual(resp.status_code, 200)
        notes = MobileNotification.objects.filter(user=self.user, data__reminder_id=self.reminder.pk)
        self.assertEqual(notes.count(), 1)
        self.assertIn(notes.get().push_status, ('', 'skipped'))

    def test_local_delivered_rejects_foreign_reminder(self):
        other = User.objects.create_user(
            username='foreign_user_v2',
            password='test',
            phone='09129993333',
        )
        foreign = Reminder.objects.create(
            user=other,
            title='غریبه',
            due_at=timezone.now() + timedelta(hours=1),
        )
        resp = self.client.post(
            '/api/mobile/v1/notifications/local-delivered',
            {'reminder_id': foreign.pk},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)


class BroadcastTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09120004444', password='test', phone='09120004444')
        MobileDevice.objects.create(
            user=self.user,
            device_id='bcast-device',
            fcm_token='tok-bcast',
            is_active=True,
        )

    def test_process_broadcast_is_idempotent(self):
        b = MobileNotificationBroadcast.objects.create(
            title='نسخه جدید',
            body='فایلینگ دیوار به‌روز شد',
            notification_type='app_update',
            deep_link='divarfiling://notifications',
            target=MobileNotificationBroadcast.TARGET_ALL,
            status=MobileNotificationBroadcast.STATUS_DRAFT,
        )
        with patch(
            'mobile_api.services.broadcast_service.send_push_to_tokens',
            return_value={'attempted': 1, 'success': 1, 'failure': 0},
        ):
            self.assertTrue(process_broadcast(b.pk))
            self.assertFalse(process_broadcast(b.pk))
        b.refresh_from_db()
        self.assertEqual(b.status, MobileNotificationBroadcast.STATUS_SENT)
        self.assertEqual(
            MobileNotification.objects.filter(user=self.user, notification_type='app_update').count(),
            1,
        )

    def test_scheduled_broadcast_waits(self):
        future = timezone.now() + timedelta(hours=2)
        b = MobileNotificationBroadcast.objects.create(
            title='بعداً',
            body='متن',
            scheduled_at=future,
            status=MobileNotificationBroadcast.STATUS_DRAFT,
        )
        queue_broadcast(b, immediate=False)
        b.refresh_from_db()
        self.assertEqual(b.status, MobileNotificationBroadcast.STATUS_SCHEDULED)

    def test_create_notification_rejects_unsafe_link(self):
        n = create_notification(
            self.user,
            notification_type='announcement',
            title='x',
            body='y',
            deep_link='https://example.com',
            send_push=False,
        )
        self.assertEqual(n.deep_link, 'divarfiling://notifications')
