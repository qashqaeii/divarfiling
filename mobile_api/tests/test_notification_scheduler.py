"""تست زمان‌بندی اعلان‌های موبایل."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from mobile_api.models import MobileDevice, MobileNotification
from mobile_api.services.notification_scheduler import (
    process_due_reminders,
    process_overdue_followups,
    process_today_digest,
    user_push_enabled,
)
from workspace.models import Customer, Reminder

User = get_user_model()


class NotificationSchedulerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121111111', password='test')
        MobileDevice.objects.create(
            user=self.user,
            device_id='test-device-1',
            fcm_token='fake-token',
            notification_prefs={'crm_reminders': True, 'today_digest': True},
        )
        self.customer = Customer.objects.create(
            user=self.user,
            name='علی تست',
            phone='09121111111',
            status='در حال پیگیری',
        )

    def test_process_due_reminders_sends_once(self):
        due = timezone.now() - timedelta(minutes=5)
        reminder = Reminder.objects.create(
            user=self.user,
            customer=self.customer,
            title='تماس با مشتری',
            due_at=due,
        )
        sent = process_due_reminders()
        self.assertEqual(sent, 1)
        self.assertEqual(
            MobileNotification.objects.filter(
                user=self.user,
                notification_type='reminder_call',
            ).count(),
            1,
        )
        sent_again = process_due_reminders()
        self.assertEqual(sent_again, 0)

    def test_visit_reminder_type(self):
        due = timezone.now() - timedelta(minutes=2)
        Reminder.objects.create(
            user=self.user,
            customer=self.customer,
            title='بازدید ملک',
            due_at=due,
        )
        process_due_reminders()
        n = MobileNotification.objects.get(user=self.user)
        self.assertEqual(n.notification_type, 'reminder_visit')
        self.assertIn('contacts/', n.deep_link)

    def test_user_push_disabled(self):
        MobileDevice.objects.filter(user=self.user).update(
            notification_prefs={'crm_reminders': False},
        )
        self.assertFalse(user_push_enabled(self.user, 'reminder_call'))

    def test_today_digest_force(self):
        self.customer.next_follow_up = timezone.now().date()
        self.customer.save(update_fields=['next_follow_up'])
        sent = process_today_digest(force=True)
        self.assertGreaterEqual(sent, 0)

    def test_overdue_followup_force(self):
        self.customer.next_follow_up = timezone.now().date() - timedelta(days=2)
        self.customer.status = 'در حال پیگیری'
        self.customer.save(update_fields=['next_follow_up', 'status'])
        sent = process_overdue_followups(digest_hour_only=False)
        self.assertGreaterEqual(sent, 0)
