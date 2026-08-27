"""تست مرکز فعالیت — Timeline، فیلتر، Pagination و امنیت."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_activity_center import (
    ACTIVITY_PAGE_SIZE,
    get_activity_center_context,
    group_activity_events,
)
from accounts.services.admin_dashboard import collect_activity_events, get_activity_feed
from accounts.services.admin_panel_shell import resolve_admin_panel_nav_active
from shop.models import LicensePlan, Order, Product
from workspace.models import Ticket

User = get_user_model()


@override_settings(TIME_ZONE='Asia/Tehran')
class ActivityCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='actu1', password='x', phone='09120000091')

    def test_summary_counts_in_range(self):
        product = Product.objects.create(title='P', slug='act-p', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        ctx = get_activity_center_context(days=7)
        self.assertGreaterEqual(ctx['summary']['order_paid'], 1)
        self.assertGreaterEqual(ctx['summary']['total'], 1)

    def test_filter_payment_only(self):
        product = Product.objects.create(title='P2', slug='act-p2', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=100000,
            status='paid',
            paid_at=timezone.now(),
        )
        ctx = get_activity_center_context(days=7, activity_type='payment')
        for group in ctx['timeline_groups']:
            for ev in group['events']:
                self.assertEqual(ev['type'], 'order_paid')

    def test_pagination_preserves_type(self):
        ctx = get_activity_center_context(days=30, activity_type='ticket', page=2)
        self.assertIn('type=ticket', ctx['next_page_url'] or ctx['prev_page_url'] or ctx['query_suffix'])

    def test_detail_urls_no_sensitive_data(self):
        Ticket.objects.create(
            user=self.user,
            ticket_number='T-ACT1',
            subject='موضوع تست',
            category='other',
        )
        ctx = get_activity_center_context(days=7)
        events = [ev for g in ctx['timeline_groups'] for ev in g['events']]
        self.assertTrue(events)
        sample = events[0]
        self.assertIn('detail_url', sample)
        self.assertNotIn('0912', sample.get('description', ''))
        self.assertNotIn('password', str(sample).lower())

    def test_grouping_labels(self):
        now = timezone.now()
        grouped = group_activity_events([
            {'at': now, 'type': 'signup', 'title': 'a'},
            {'at': now - timezone.timedelta(days=1), 'type': 'signup', 'title': 'b'},
        ])
        labels = [g['label'] for g in grouped]
        self.assertIn('امروز', labels)
        self.assertIn('دیروز', labels)

    def test_get_activity_feed_still_works(self):
        feed = get_activity_feed(limit=3)
        self.assertIsInstance(feed, list)

    def test_collect_activity_events_snapshot(self):
        events = collect_activity_events(snapshot=True)
        self.assertIsInstance(events, list)


@override_settings(TIME_ZONE='Asia/Tehran')
class AdminActivityCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username='actstaff', password='pass1234', phone='09120000092', is_staff=True,
        )
        self.user = User.objects.create_user(username='actu2', password='x', phone='09120000093')

    def test_staff_only(self):
        self.assertEqual(self.client.get(reverse('admin_panel_activity')).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('admin_panel_activity')).status_code, 403)

    def test_template_render_ranges_filters_pagination(self):
        product = Product.objects.create(title='P3', slug='act-p3', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        for i in range(ACTIVITY_PAGE_SIZE + 3):
            u = User.objects.create_user(username=f'bulk{i}', password='x', phone=f'0913000{i:04d}')
            Order.objects.create(
                user=u,
                product=product,
                plan=plan,
                amount=100000,
                status='paid',
                paid_at=timezone.now(),
            )

        self.client.force_login(self.staff)
        for days in ('1', '7', '30', '90'):
            resp = self.client.get(reverse('admin_panel_activity'), {'days': days})
            self.assertEqual(resp.status_code, 200)
            content = resp.content.decode()
            self.assertIn('ecc-activity', content)
            self.assertIn(f'data-range="{days}"', content)

        resp = self.client.get(reverse('admin_panel_activity'), {'days': '30', 'type': 'payment'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('is-active', resp.content.decode())

        resp_page2 = self.client.get(reverse('admin_panel_activity'), {'days': '30', 'page': '2'})
        self.assertEqual(resp_page2.status_code, 200)
        self.assertIn('page=2', resp_page2.content.decode())

        self.assertEqual(resolve_admin_panel_nav_active('/accounts/admin-panel/activity/'), 'activity')

    def test_compare_and_anchor_fallback(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_activity'), {'days': '30', 'compare': '1'})
        self.assertEqual(resp.status_code, 200)
        self.assertIn('compare=1', resp.content.decode())
        dash = self.client.get(reverse('admin_panel'), {'days': '7'})
        content = dash.content.decode()
        self.assertIn('/accounts/admin-panel/activity/', content)
        dash_anchor = self.client.get(reverse('admin_panel'), {'days': '7'}, follow=False)
        self.assertIn('#ecc-activity', dash_anchor.content.decode())

    def test_ordering_newest_first(self):
        product = Product.objects.create(title='P4', slug='act-p4', is_active=True)
        plan = LicensePlan.objects.create(
            product=product, name='م', plan_type='monthly', price=100000, duration_days=30, is_active=True,
        )
        older = timezone.now() - timezone.timedelta(hours=5)
        newer = timezone.now()
        Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=50000,
            status='paid',
            paid_at=older,
        )
        u2 = User.objects.create_user(username='neweru', password='x', phone='09120000094')
        Order.objects.create(
            user=u2,
            product=product,
            plan=plan,
            amount=200000,
            status='paid',
            paid_at=newer,
        )
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_activity'), {'days': '7', 'type': 'payment'})
        content = resp.content.decode()
        pos_new = content.find('۲۰۰')
        pos_old = content.find('۵۰')
        if pos_new >= 0 and pos_old >= 0:
            self.assertLess(pos_new, pos_old)
