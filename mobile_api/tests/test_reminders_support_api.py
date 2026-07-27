"""تست API یادآورها و تیکت پشتیبانی (Sprint 1)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from workspace.models import Reminder
from workspace.services.support_tickets import create_ticket
from workspace.support_constants import TICKET_CATEGORY_OTHER, TICKET_PRIORITY_NORMAL

User = get_user_model()


class RemindersApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09121112233', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.due = timezone.now() + timedelta(hours=2)

    def test_create_list_snooze_complete_reminder(self):
        create = self.client.post(
            '/api/mobile/v1/crm/reminders',
            {
                'title': 'تماس با مشتری',
                'due_at': self.due.isoformat(),
                'note': 'پیگیری قرارداد',
                'recurrence': 'daily',
            },
            format='json',
        )
        self.assertEqual(create.status_code, 201, create.content)
        data = create.json()['data']
        self.assertEqual(data['title'], 'تماس با مشتری')
        self.assertEqual(data['recurrence'], 'daily')
        rid = data['id']

        listed = self.client.get('/api/mobile/v1/crm/reminders', {'done': 'false'})
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(item['id'] == rid for item in listed.json()['data']))

        snooze = self.client.patch(
            f'/api/mobile/v1/crm/reminders/{rid}',
            {'action': 'snooze', 'hours': 1},
            format='json',
        )
        self.assertEqual(snooze.status_code, 200)
        after_snooze = Reminder.objects.get(pk=rid).due_at
        self.assertGreater(after_snooze, self.due)

        complete = self.client.patch(
            f'/api/mobile/v1/crm/reminders/{rid}',
            {'action': 'complete'},
            format='json',
        )
        self.assertEqual(complete.status_code, 200)
        rem = Reminder.objects.get(pk=rid)
        self.assertTrue(rem.is_done)
        self.assertTrue(
            Reminder.objects.filter(user=self.user, is_done=False, recurrence='daily').exists()
        )


class SupportTicketThreadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='09124445566', password='test')
        self.client = APIClient()
        token = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        self.ticket = create_ticket(
            user=self.user,
            subject='مشکل ورود',
            category=TICKET_CATEGORY_OTHER,
            priority=TICKET_PRIORITY_NORMAL,
            body='نمی‌توانم وارد اپ شوم',
        )

    def test_detail_reply_close_reopen(self):
        detail = self.client.get(f'/api/mobile/v1/support/tickets/{self.ticket.pk}')
        self.assertEqual(detail.status_code, 200)
        payload = detail.json()['data']
        self.assertEqual(payload['id'], self.ticket.pk)
        self.assertIn('messages', payload)
        self.assertGreaterEqual(len(payload['messages']), 1)

        reply = self.client.post(
            f'/api/mobile/v1/support/tickets/{self.ticket.pk}/reply',
            {'body': 'هنوز مشکل دارم'},
            format='multipart',
        )
        self.assertEqual(reply.status_code, 201, reply.content)
        self.assertTrue(reply.json()['ok'])

        close = self.client.post(f'/api/mobile/v1/support/tickets/{self.ticket.pk}/close')
        self.assertEqual(close.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, 'closed')

        reopen = self.client.post(f'/api/mobile/v1/support/tickets/{self.ticket.pk}/reopen')
        self.assertEqual(reopen.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertNotEqual(self.ticket.status, 'closed')
