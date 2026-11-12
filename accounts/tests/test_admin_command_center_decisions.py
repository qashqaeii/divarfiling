"""Phase 03A: Command Center decisions are precise and role-aware."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_command_queues import (
    _queue_stats,
    build_command_action_items,
    get_command_queue_spec,
    qs_unread_tickets,
)
from accounts.services.admin_dashboard import build_command_modules
from accounts.services.admin_presentation import prioritize_management_actions
from shop.models import LicensePlan, Order, Product
from workspace.models import Ticket

User = get_user_model()


class CommandQueueUrgencyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='command03_user', password='pass',
            phone='09129996201',
        )

    def test_unread_tickets_without_last_message_use_creation_age(self):
        ticket = Ticket.objects.create(
            user=self.user,
            ticket_number='CMD03A001',
            subject='پاسخ داده نشده',
            category='general',
            staff_has_unread=True,
            last_message_at=None,
        )
        previous = timezone.now() - timedelta(days=3)
        Ticket.objects.filter(pk=ticket.pk).update(created_at=previous)
        qs = qs_unread_tickets()
        with self.assertNumQueries(1):
            meta = _queue_stats(qs, oldest_field='last_message_at')
        self.assertEqual(meta['count'], 1)
        self.assertEqual(meta['oldest_at'], previous)
        self.assertIn('روز', meta['oldest_label'])

    def test_oldest_event_ignores_nulls_without_losing_older_ticket(self):
        first = Ticket.objects.create(
            user=self.user, ticket_number='CMD03A002',
            subject='بدون زمان پیام', category='general',
            staff_has_unread=True, last_message_at=None,
        )
        Ticket.objects.filter(pk=first.pk).update(
            created_at=timezone.now() - timedelta(days=5),
        )
        second = Ticket.objects.create(
            user=self.user, ticket_number='CMD03A003',
            subject='پاسخ جدید', category='general',
            staff_has_unread=True, last_message_at=timezone.now() - timedelta(hours=2),
        )
        meta = _queue_stats(qs_unread_tickets(), oldest_field='last_message_at')
        self.assertEqual(meta['count'], 2)
        self.assertEqual(meta['oldest_at'].date(), (timezone.now() - timedelta(days=5)).date())
        self.assertLess(meta['oldest_at'], second.last_message_at)

    def test_paid_order_without_paid_at_uses_created_at(self):
        product = Product.objects.create(title='Command product', slug='command03-product', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='ماهانه', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        order = Order.objects.create(
            user=self.user, product=product, plan=plan, amount=100000,
            status='paid', paid_at=None,
        )
        older = timezone.now() - timedelta(days=2)
        Order.objects.filter(pk=order.pk).update(created_at=older)
        meta = _queue_stats(Order.objects.filter(pk=order.pk), oldest_field='paid_at')
        self.assertEqual(meta['oldest_at'], older)

    def test_sms_credit_is_not_misrepresented_as_a_case_count(self):
        items = build_command_action_items(sms_balance={
            'ok': True, 'is_low': True, 'credit': 40000,
        })
        sms = next(item for item in items if item['key'] == 'sms_low')
        self.assertIsNone(sms['count'])
        self.assertIn('40,000 تومان', sms['oldest_label'])
        self.assertEqual(sms['cta'], 'بررسی اعتبار')
        self.assertEqual(
            [x['key'] for x in items],
            [x['key'] for x in prioritize_management_actions(items)],
        )

    def test_queue_destinations_are_existing_filtered_pages(self):
        for key, fragment in (
            ('fulfillment_incomplete', '#sales-queue-fulfillment'),
            ('orders_failed_today', '#sales-table-failed'),
            ('unread_tickets', '#support-table-tickets'),
            ('orders_pending', '#sales-table-pending'),
            ('pending_withdrawals', '#affiliate-withdrawals'),
        ):
            with self.subTest(key=key):
                spec = get_command_queue_spec(key)
                self.assertIsNotNone(spec)
                self.assertIn(fragment, spec['href']())


class CommandCenterRoleAndPresentationTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='command03_staff', password='pass',
            phone='09129996202', is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='command03_owner', password='pass',
            phone='09129996203', is_staff=True, is_superuser=True,
        )

    def test_basic_staff_sees_actions_without_unusable_exports_or_owner_shortcuts(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'کدام مورد نیاز به اقدام دارد؟')
        self.assertNotContains(
            response, reverse('admin_panel_export', args=['paid_orders']) + '?format=xlsx',
        )
        self.assertNotContains(
            response, reverse('admin_panel_export', args=['all_users']) + '?format=xlsx',
        )
        self.assertNotContains(
            response, reverse('admin_panel_export', args=['expiring_licenses']) + '?format=xlsx',
        )
        self.assertFalse(any(
            module.get('href') == '/admin/'
            for module in response.context['command_modules']
        ))

    def test_owner_has_all_authorized_shortcuts(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel'), {'days': '7'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse('admin_panel_export', args=['paid_orders']) + '?format=xlsx',
        )
        self.assertTrue(any(
            module.get('href') == '/admin/'
            for module in response.context['command_modules']
        ))

    def test_command_decision_summary_describes_priorities_not_money(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('command_decision_summary', response.context)
        self.assertNotIn('تومان', response.context['command_decision_summary'])

    def test_django_admin_shortcut_has_no_irrelevant_queue_badge(self):
        modules = build_command_modules({'orders_pending': 3}, alert_count=9)
        owner_link = next(m for m in modules if m.get('href') == '/admin/')
        self.assertIsNone(owner_link['badge'])
