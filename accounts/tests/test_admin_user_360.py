"""تست پرونده ۳۶۰ مشتری در پنل مدیریت."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from accounts.services.admin_action_permissions import can_manage_support_tickets, can_view_user_management
from accounts.services.admin_user_360 import build_user_360_tab
from accounts.services.admin_user_360.tabs import extraction_usage_snapshot, tab_usage
from workspace.models import Dataset, Ticket, TicketMessage
from workspace.support_constants import TICKET_CATEGORY_OTHER, TICKET_STATUS_OPEN
from accounts.services.admin_user_360.common import sms_purpose_label
from accounts.services.growth_journey import growth_journey_event_label
from shop.models import Order, Product, LicensePlan

User = get_user_model()


class AdminUser360PermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='u360_cust',
            phone='09128880001',
            password='test-pass-123',
        )
        self.staff = User.objects.create_user(
            username='u360_staff',
            phone='09128880002',
            password='test-pass-123',
            is_staff=True,
        )

    def _grant_user_management(self, user):
        for app, model in (
            ('accounts', 'user'),
            ('shop', 'order'),
            ('licenses', 'license'),
        ):
            ct = ContentType.objects.get(app_label=app, model=model)
            perm = Permission.objects.get(content_type=ct, codename=f'view_{model}')
            user.user_permissions.add(perm)

    def test_customer_cannot_open_profile(self):
        self.client.force_login(self.customer)
        resp = self.client.get(reverse('admin_panel_user_360', args=[self.customer.id]))
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_staff_without_perm_gets_403(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_user_360', args=[self.customer.id]))
        self.assertEqual(resp.status_code, 403)

    def test_404_for_missing_user(self):
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_user_360', args=[99999999]))
        self.assertEqual(resp.status_code, 404)

    def test_authorized_staff_sees_profile(self):
        self._grant_user_management(self.staff)
        self.assertTrue(can_view_user_management(self.staff))
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_user_360', args=[self.customer.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'adm-u360-page')
        self.assertContains(resp, self.customer.phone)

    def test_tab_json_requires_permission(self):
        url = reverse('admin_panel_user_360_tab_json', args=[self.customer.id, 'account'])
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self._grant_user_management(self.staff)
        self.client.force_login(self.staff)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertEqual(data['tab'], 'account')

    def test_tab_json_accepts_panel_days_all(self):
        self._grant_user_management(self.staff)
        self.client.force_login(self.staff)
        for tab in ('account', 'agency', 'overview', 'activity'):
            url = reverse('admin_panel_user_360_tab_json', args=[self.customer.id, tab])
            resp = self.client.get(url, {'days': 'all'})
            self.assertEqual(resp.status_code, 200, msg=tab)
            data = resp.json()
            self.assertTrue(data.get('ok'), msg=tab)
            self.assertEqual(data['tab'], tab)


class AdminUser360LocalizationTests(TestCase):
    def test_sms_purpose_labels_are_persian(self):
        self.assertEqual(sms_purpose_label('login'), 'ورود')
        self.assertEqual(sms_purpose_label('register'), 'ثبت‌نام')
        self.assertEqual(sms_purpose_label('marketing'), 'بازاریابی')
        self.assertEqual(sms_purpose_label('LOGIN'), 'ورود')

    def test_growth_journey_event_labels_are_persian(self):
        self.assertEqual(growth_journey_event_label('signup'), 'ثبت‌نام')
        self.assertEqual(growth_journey_event_label('checkout_start'), 'شروع خرید')
        self.assertEqual(growth_journey_event_label('paid_licensed'), 'پرداخت و فعال‌سازی لایسنس')


class AdminUser360DataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='u360_data',
            phone='09128880011',
            password='test-pass-123',
        )

    def test_commerce_excludes_granted_from_revenue(self):
        product = Product.objects.first()
        plan = LicensePlan.objects.first()
        if not product or not plan:
            self.skipTest('نیاز به داده فروشگاه')
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=500_000,
            status='granted',
        )
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=1_000_000,
            status='paid',
        )
        payload = build_user_360_tab(self.user.id, 'commerce')
        self.assertIsNotNone(payload)
        self.assertEqual(payload['data']['summary']['total_revenue_paid_only'], 1_000_000)
        self.assertIn('charts', payload['data'])
        self.assertIn('orders_by_status', payload['data']['charts'])

    def test_usage_extraction_counts_windows_path_without_mobile_runs(self):
        Dataset.objects.create(
            user=self.user,
            name='فایل تست',
            original_filename='divar.xlsx',
            file_format='xlsx',
            row_count=76,
        )
        summary = {'usage': {'listings': 76, 'datasets': 1}}
        started, count, _last_at, note = extraction_usage_snapshot(self.user, summary['usage'])
        self.assertTrue(started)
        self.assertGreaterEqual(count, 1)
        self.assertIn('ویندوز', note)

        payload = tab_usage(self.user, summary)
        by_name = {f['name']: f for f in payload['features']}
        ext = by_name['استخراج آگهی']
        self.assertTrue(ext['started'])
        self.assertGreaterEqual(int(ext['count']), 1)
        self.assertIn('ویندوز', ext.get('note') or '')

    def test_xss_escaped_in_template_context(self):
        xss = User.objects.create_user(
            username='xss_user',
            phone='09128880022',
            password='test-pass-123',
            first_name='<script>alert(1)</script>',
        )
        staff = User.objects.create_user(
            username='xss_staff',
            phone='09128880033',
            password='test-pass-123',
            is_staff=True,
            is_superuser=True,
        )
        client = Client()
        client.force_login(staff)
        resp = client.get(reverse('admin_panel_user_360', args=[xss.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, '<script>alert(1)</script>')


class AdminUser360SupportTicketTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = User.objects.create_user(
            username='u360_ticket_cust',
            phone='09128880101',
            password='test-pass-123',
        )
        self.staff = User.objects.create_user(
            username='u360_ticket_staff',
            phone='09128880102',
            password='test-pass-123',
            is_staff=True,
            is_superuser=True,
        )
        self.ticket = Ticket.objects.create(
            user=self.customer,
            ticket_number='DF-TEST-000001',
            subject='تست تیکت',
            description='شرح اولیه',
            category=TICKET_CATEGORY_OTHER,
            status=TICKET_STATUS_OPEN,
        )
        TicketMessage.objects.create(
            ticket=self.ticket,
            author=self.customer,
            body='سلام، سوال دارم.',
            is_staff_reply=False,
        )

    def test_staff_reply_via_u360_action(self):
        self.client.force_login(self.staff)
        self.assertTrue(can_manage_support_tickets(self.staff))
        url = reverse('admin_panel_user_360_ticket_action', args=[self.customer.id, self.ticket.pk])
        resp = self.client.post(
            url,
            data='{"action":"reply","body":"پاسخ پشتیبانی"}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('ok'))
        self.assertTrue(
            TicketMessage.objects.filter(ticket=self.ticket, is_staff_reply=True, body__contains='پاسخ').exists()
        )

    def test_ticket_detail_json_scoped_to_user(self):
        other = User.objects.create_user(username='other_u', phone='09128880103', password='x')
        foreign = Ticket.objects.create(
            user=other,
            ticket_number='DF-TEST-000002',
            subject='دیگر',
            category=TICKET_CATEGORY_OTHER,
            status=TICKET_STATUS_OPEN,
        )
        self.client.force_login(self.staff)
        url = reverse('admin_panel_user_360_ticket_detail', args=[self.customer.id, foreign.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
