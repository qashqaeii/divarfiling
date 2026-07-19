"""Tests for Recovery Center admin data product (Week 1 MVP)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun
from accounts.services.admin_recovery_center import (
    SCHEMA_VERSION,
    build_recovery_center_json,
    get_recovery_center_context,
    is_production_recovery_send,
)
from accounts.services.pending_recovery import FLOW_KEY, STEP_RECOVERY_1
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product

User = get_user_model()


def _staff():
    return User.objects.create_user(
        username='rc_staff',
        email='rc@example.com',
        password='x',
        is_staff=True,
    )


def _product_plan():
    product = Product.objects.create(
        title='Recovery Test Product',
        slug='rc-test-product',
        description='t',
        is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name='Monthly',
        plan_type='monthly',
        price=500_000,
        duration_days=30,
        is_active=True,
    )
    return product, plan


class RecoveryCenterServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer1',
            email='b1@example.com',
            password='x',
            phone='09121111111',
        )
        self.product, self.plan = _product_plan()

    def test_json_schema_and_freshness(self):
        payload = build_recovery_center_json(days=30)
        self.assertEqual(payload['schema_version'], SCHEMA_VERSION)
        self.assertIn('generated_at', payload)
        self.assertIn('data_freshness', payload)
        self.assertIn('last_event_at', payload['data_freshness'])
        self.assertIn('last_recovery_run_at', payload['data_freshness'])
        self.assertIn('funnel', payload)
        self.assertIn('data_quality', payload)
        self.assertIsNone(payload['funnel']['executive']['recovered'])

    def test_funnel_counts_abandon_event(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=500_000,
            status='pending',
        )
        PlanFunnelEvent.objects.create(
            event_type='checkout_abandon',
            user=self.user,
            order=order,
            product=self.product,
            plan=self.plan,
        )
        ctx = get_recovery_center_context(days=30)
        self.assertGreaterEqual(ctx['summary']['abandoned'], 1)

    def test_journey_counts_production_send(self):
        run = MarketingAutomationRun.objects.create(
            flow_key=FLOW_KEY,
            mode=MarketingAutomationRun.Mode.LIVE,
            status=MarketingAutomationRun.Status.COMPLETED,
        )
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=500_000,
            status='pending',
        )
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            user=self.user,
            phone_hash='abc123',
            masked_phone='0912***11',
            order=order,
            product=self.product,
            action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            decision_key='decision:test-send-1',
            send_idempotency_key='send:step1:abc:1',
        )
        ctx = get_recovery_center_context(days=30)
        step1 = next(r for r in ctx['journey'] if r['step_key'] == STEP_RECOVERY_1)
        self.assertEqual(step1['sent'], 1)
        self.assertGreaterEqual(ctx['summary']['sms_accepted'], 1)

    def test_test_send_excluded_from_production_kpi(self):
        run = MarketingAutomationRun.objects.create(flow_key=FLOW_KEY)
        log = MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            phone_hash='testhash',
            masked_phone='0912***99',
            action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            decision_key='decision:test-only-1',
            send_idempotency_key='test:send:1',
        )
        self.assertFalse(is_production_recovery_send(log))

    def test_data_quality_abandon_without_user(self):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=500_000,
            status='pending',
        )
        PlanFunnelEvent.objects.create(
            event_type='checkout_abandon',
            user=None,
            order=order,
            product=self.product,
            plan=self.plan,
        )
        PlanFunnelEvent.objects.create(
            event_type='checkout_abandon',
            user=self.user,
            order=order,
            product=self.product,
            plan=self.plan,
        )
        ctx = get_recovery_center_context(days=30)
        dq = ctx['data_quality']
        self.assertEqual(dq['checkout_abandon_total'], 2)
        self.assertEqual(dq['checkout_abandon_without_user_count'], 1)
        self.assertEqual(dq['checkout_abandon_without_user_pct'], 50.0)

    def test_attribution_rules_documented(self):
        ctx = get_recovery_center_context(days=30)
        rules = ctx['attribution_rules']
        self.assertEqual(rules['executive_kpi'], 'strict_only')
        self.assertIn('strict_primary', rules)


class AdminRecoveryCenterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = _staff()

    def test_guest_redirected(self):
        resp = self.client.get(reverse('admin_panel_recovery_center'))
        self.assertEqual(resp.status_code, 302)

    def test_staff_can_open_page(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_recovery_center'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'مرکز بازیابی')
        self.assertContains(resp, 'درآمد بازیابی‌شده')

    def test_json_endpoint(self):
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_recovery_center_json'), {'days': 30})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['schema_version'], SCHEMA_VERSION)
        self.assertIn('data_freshness', data)

    def test_explorer_lists_action_log(self):
        run = MarketingAutomationRun.objects.create(flow_key=FLOW_KEY)
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            phone_hash='explore1',
            masked_phone='0912***22',
            action=MarketingAutomationActionLog.Action.WOULD_SEND,
            decision_key='decision:explorer-1',
        )
        self.client.force_login(self.staff)
        resp = self.client.get(reverse('admin_panel_recovery_center'))
        self.assertContains(resp, 'ارسال شبیه‌سازی')
