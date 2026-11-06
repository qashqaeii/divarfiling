"""تست KPI پریمیوم صفحه پشتیبانی."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from workspace.models import Ticket
from workspace.services.support_tickets import build_support_kpi_stats, get_user_ticket_stats
from workspace.support_constants import (
    TICKET_STATUS_CLOSED,
    TICKET_STATUS_OPEN,
    TICKET_STATUS_WAITING_USER,
)

User = get_user_model()


class SupportKpiStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09128880011',
            phone='09128880011',
            password='pass12345',
        )

    def test_empty_stats(self):
        kpi = build_support_kpi_stats(self.user)
        self.assertEqual(kpi['total'], 0)
        self.assertEqual(kpi['open'], 0)
        self.assertEqual(kpi['hero_meta'], 'هنوز تیکتی ثبت نکرده‌اید')
        base = get_user_ticket_stats(self.user)
        for key in ('total', 'open', 'waiting_user', 'closed', 'unread_replies'):
            self.assertEqual(kpi[key], base[key])

    def test_mix_and_shares(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-OPEN-1',
            subject='باز',
            category='other',
            priority='normal',
            status=TICKET_STATUS_OPEN,
            description='x',
        )
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-WAIT-1',
            subject='منتظر',
            category='other',
            priority='normal',
            status=TICKET_STATUS_WAITING_USER,
            description='x',
            user_has_unread=True,
        )
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-CLOSE-1',
            subject='بسته',
            category='other',
            priority='normal',
            status=TICKET_STATUS_CLOSED,
            description='x',
        )
        kpi = build_support_kpi_stats(self.user)
        self.assertEqual(kpi['total'], 3)
        self.assertEqual(kpi['open'], 2)
        self.assertEqual(kpi['waiting_user'], 1)
        self.assertEqual(kpi['closed'], 1)
        self.assertEqual(kpi['unread_replies'], 1)
        self.assertTrue(kpi['mix_segments'])
        self.assertIn('منتظر پاسخ شماست', kpi['waiting_meta'])


class SupportPageKpiRenderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09128880022',
            phone='09128880022',
            password='pass12345',
        )
        self.client = Client()
        self.client.force_login(self.user)
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-PAGE-1',
            subject='تیکت صفحه',
            category='other',
            priority='normal',
            status=TICKET_STATUS_WAITING_USER,
            description='body',
        )

    def test_list_renders_premium_kpi(self):
        url = reverse('workspace:support_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'fl-kpi-pro--support')
        self.assertContains(resp, 'همه تیکت‌ها')
        self.assertContains(resp, 'منتظر شما')
        self.assertEqual(resp.context['stats']['waiting_user'], 1)

        waiting = self.client.get(url, {'status': 'waiting_user'})
        self.assertEqual(waiting.status_code, 200)
        self.assertEqual(waiting.context['status_filter'], 'waiting_user')
        self.assertEqual(len(waiting.context['tickets']), 1)
