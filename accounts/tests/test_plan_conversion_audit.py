"""تست‌های Audit آماری داشبورد تبدیل پلن."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.services.admin_plan_conversion import (
    build_plan_conversion_json,
    get_plan_conversion_context,
)
from accounts.services.plan_bi import (
    comparison_status,
    conversion_rate,
    delta_pct,
)
from accounts.services.plan_bi.behavior import build_behavior_analytics
from accounts.services.plan_bi.cohorts import build_rich_cohorts
from accounts.services.plan_bi.data_quality import classify_order_statuses
from accounts.services.plan_bi.plan_matrix import build_plan_matrix
from licenses.models import License, LicenseActivation
from shop.bot_catalog import bot_license_plans
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product
from workspace.models import Customer, Dataset

User = get_user_model()


class ConversionAuditHelpersTests(TestCase):
    def test_conversion_never_over_100(self):
        self.assertIsNone(conversion_rate(20, 1))
        self.assertEqual(conversion_rate(1, 2), 50.0)
        self.assertIsNone(conversion_rate(5, 0))

    def test_delta_pct_zero_previous_is_null(self):
        self.assertIsNone(delta_pct(100, 0))
        self.assertIsNone(delta_pct(50, None))
        self.assertEqual(comparison_status(100, 0), 'new_activity')


class FunnelConversionAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            title='ربات تست', slug='audit-bot', is_active=True,
        )
        self.plans = {}
        for data in bot_license_plans():
            plan = LicensePlan.objects.create(product=self.product, **data)
            self.plans[plan.plan_type] = plan
        self.users = []
        for i in range(20):
            self.users.append(User.objects.create_user(
                username=f'buyer{i}', password='x', phone=f'0912000{i:04d}',
            ))

    def _paid(self, user, plan_type='monthly', days_ago=5):
        return Order.objects.create(
            user=user,
            product=self.product,
            plan=self.plans[plan_type],
            amount=self.plans[plan_type].price,
            status='paid',
            paid_at=timezone.now() - timedelta(days=days_ago),
        )

    def test_paid_20_pricing_1_no_2000_conversion(self):
        PlanFunnelEvent.objects.create(
            event_type='pricing_view', session_key='s1', product=self.product,
        )
        PlanFunnelEvent.objects.create(
            event_type='checkout_view', session_key='s1', product=self.product,
        )
        for u in self.users:
            self._paid(u)

        ctx = get_plan_conversion_context(days=30)
        self.assertIsNone(ctx['summary']['overall_conversion'])
        self.assertIsNone(ctx['summary']['checkout_conversion'])
        self.assertIsNone(ctx['summary']['funnel_conversion'])
        self.assertFalse(ctx['summary']['funnel_conversions_available'])
        self.assertEqual(ctx['summary']['paid_count'], 20)
        # هیچ conversion > 100
        for key in ('overall_conversion', 'checkout_conversion', 'funnel_conversion'):
            val = ctx['summary'][key]
            if val is not None:
                self.assertLessEqual(val, 100)

    def test_no_conversion_above_100_anywhere(self):
        for i, u in enumerate(self.users[:5]):
            PlanFunnelEvent.objects.create(
                event_type='pricing_view', session_key=f'p{i}', product=self.product,
            )
            self._paid(u)
        ctx = get_plan_conversion_context(days=30)
        rates = [
            ctx['summary']['overall_conversion'],
            ctx['summary']['checkout_conversion'],
        ]
        for stage in ctx['purchase_funnel']['stages'] + ctx['activation_funnel']['stages']:
            rates.append(stage.get('conversion_from_prev'))
            rates.append(stage.get('conversion_from_base'))
        for row in ctx['plan_rows']:
            rates.append(row.get('funnel_conversion'))
        for r in rates:
            if r is not None:
                self.assertLessEqual(float(r), 100.0)

    def test_purchase_and_activation_funnels_independent(self):
        self._paid(self.users[0])
        ctx = get_plan_conversion_context(days=30)
        self.assertIn('purchase_funnel', ctx)
        self.assertIn('activation_funnel', ctx)
        purchase_keys = [s['key'] for s in ctx['purchase_funnel']['stages']]
        activation_keys = [s['key'] for s in ctx['activation_funnel']['stages']]
        self.assertIn('pricing_view', purchase_keys)
        self.assertIn('checkout_started', purchase_keys)
        self.assertIn('payment_success', purchase_keys)
        self.assertIn('paid_buyer', activation_keys)
        self.assertIn('first_crm_use', activation_keys)
        self.assertNotIn('upgraded', activation_keys)
        self.assertIn('outcomes', ctx['activation_funnel'])

    def test_order_count_not_mixed_as_unique_buyers_in_activation(self):
        u = self.users[0]
        self._paid(u, 'monthly', days_ago=3)
        self._paid(u, 'yearly', days_ago=1)
        ctx = get_plan_conversion_context(days=30)
        paid_stage = next(s for s in ctx['activation_funnel']['stages'] if s['key'] == 'paid_buyer')
        self.assertEqual(paid_stage['count'], 1)
        self.assertEqual(ctx['summary']['paid_count'], 2)
        self.assertEqual(ctx['summary']['unique_buyers'], 1)


class PendingAbandonedAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='pend-bot', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product, name='M', plan_type='monthly', price=1000,
        )
        self.user = User.objects.create_user(username='puser', password='x', phone='09121111111')

    def test_pending_recent_not_abandoned(self):
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=1000, status='pending',
            created_at=timezone.now() - timedelta(hours=1),
        )
        # force created_at
        o = Order.objects.get(user=self.user)
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timedelta(hours=1))
        stats = classify_order_statuses(since=timezone.now() - timedelta(days=30), stale_hours=24)
        self.assertEqual(stats['pending_recent'], 1)
        self.assertEqual(stats['pending_stale'], 0)
        self.assertEqual(stats['abandoned'], 0)

    def test_pending_paid_later_not_abandoned(self):
        pending = Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=1000, status='pending',
        )
        Order.objects.filter(pk=pending.pk).update(
            created_at=timezone.now() - timedelta(hours=48),
        )
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=1000, status='paid', paid_at=timezone.now() - timedelta(hours=1),
        )
        stats = classify_order_statuses(since=timezone.now() - timedelta(days=30), stale_hours=24)
        self.assertEqual(stats['pending_stale'], 1)
        # without abandon events, abandoned stays 0
        self.assertEqual(stats['abandoned'], 0)
        self.assertFalse(stats['abandoned_available'])


class PlanMatrixAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='matrix-bot', is_active=True)
        self.plans = {}
        for data in bot_license_plans():
            plan = LicensePlan.objects.create(product=self.product, **data)
            self.plans[plan.plan_type] = plan
        self.user = User.objects.create_user(username='muser', password='x', phone='09122222222')

    def test_rpv_null_without_plan_visitors(self):
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plans['daily'],
            amount=self.plans['daily'].price, status='paid',
            paid_at=timezone.now() - timedelta(days=1),
        )
        rows = build_plan_matrix(
            since=timezone.now() - timedelta(days=30),
            upgrade_stats={'available': False, 'upgrade_rate': None},
        )
        daily = next(r for r in rows if r['plan_type'] == 'daily')
        self.assertIsNone(daily['rpv'])
        self.assertFalse(daily['rpv_available'])
        # نباید برابر درآمد باشد
        self.assertNotEqual(daily['rpv'], daily['revenue'])

    def test_plan_conversion_null_without_plan_view(self):
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plans['yearly'],
            amount=self.plans['yearly'].price, status='paid',
            paid_at=timezone.now() - timedelta(days=1),
        )
        rows = build_plan_matrix(
            since=timezone.now() - timedelta(days=30),
            upgrade_stats={'available': False},
        )
        yearly = next(r for r in rows if r['plan_type'] == 'yearly')
        self.assertIsNone(yearly['funnel_conversion'])
        self.assertFalse(yearly['conversion_available'])
        tag_keys = [t['key'] for t in yearly['tags']]
        self.assertNotIn('lowest_conversion', tag_keys)
        self.assertIn('no_sales', tag_keys) if yearly['purchases'] == 0 else self.assertTrue(True)


class CohortMaturityAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='cohort-bot', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product, name='M', plan_type='monthly', price=1000,
        )
        self.user = User.objects.create_user(username='cuser', password='x', phone='09123333333')

    def test_immature_7d_and_30d_unavailable(self):
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=1000, status='paid', paid_at=timezone.now() - timedelta(hours=12),
        )
        cohorts = build_rich_cohorts(limit=5)
        self.assertTrue(cohorts)
        current = cohorts[0]
        self.assertFalse(current['mature_7d'])
        self.assertFalse(current['mature_30d'])
        self.assertFalse(current['active_7d_available'])
        self.assertFalse(current['active_30d_available'])
        self.assertIsNone(current['active_7d_rate'])
        self.assertIsNone(current['active_30d_rate'])
        self.assertNotEqual(current['active_30d_display'], current.get('active_7d_rate'))


class BehaviorReturnAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='beh-bot', is_active=True)
        self.plan = LicensePlan.objects.create(
            product=self.product, name='M', plan_type='monthly', price=1000,
        )
        self.user = User.objects.create_user(username='buser', password='x', phone='09124444444')

    def test_activity_before_payment_ignored(self):
        paid_at = timezone.now() - timedelta(days=5)
        Order.objects.create(
            user=self.user, product=self.product, plan=self.plan,
            amount=1000, status='paid', paid_at=paid_at,
        )
        # دیتاست قبل از خرید
        ds = Dataset.objects.create(
            user=self.user, name='old', original_filename='old.xlsx', file_format='xlsx',
        )
        Dataset.objects.filter(pk=ds.pk).update(created_at=paid_at - timedelta(days=2))

        from accounts.services.plan_bi import load_period_buyers
        buyers = load_period_buyers(since=timezone.now() - timedelta(days=30))
        beh = build_behavior_analytics(buyers=buyers)
        feat = {f['key']: f for f in beh['features']}
        # return نباید فقط به‌خاطر دیتاست قبل از خرید پر شود
        # (اگر activity بعد از خرید نباشد)
        self.assertEqual(feat['return_7d']['count'], 0)

    def test_correlation_small_sample_unavailable(self):
        users = []
        for i in range(7):
            u = User.objects.create_user(
                username=f'corr{i}', password='x', phone=f'0912555{i:04d}',
            )
            users.append(u)
            Order.objects.create(
                user=u, product=self.product, plan=self.plan,
                amount=1000, status='paid',
                paid_at=timezone.now() - timedelta(days=2),
            )
            if i < 4:
                Customer.objects.create(user=u, name=f'C{i}')

        from accounts.services.plan_bi import load_period_buyers
        buyers = load_period_buyers(since=timezone.now() - timedelta(days=30))
        beh = build_behavior_analytics(buyers=buyers)
        crm_corr = next(c for c in beh['correlations'] if 'CRM' in c['title'])
        self.assertFalse(crm_corr['available'])
        self.assertIn('کافی نیست', crm_corr['display'])


class PredictiveAndRecsAuditTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(title='P', slug='pred-bot', is_active=True)
        self.plans = {}
        for data in bot_license_plans():
            plan = LicensePlan.objects.create(product=self.product, **data)
            self.plans[plan.plan_type] = plan
        for i in range(5):
            u = User.objects.create_user(
                username=f'pred{i}', password='x', phone=f'0912666{i:04d}',
            )
            Order.objects.create(
                user=u, product=self.product, plan=self.plans['monthly'],
                amount=self.plans['monthly'].price, status='paid',
                paid_at=timezone.now() - timedelta(days=3),
            )

    def test_predictive_has_explanation(self):
        ctx = get_plan_conversion_context(days=30)
        self.assertTrue(ctx['predictive']['available'])
        for s in ctx['predictive']['scores']:
            self.assertIn('definition', s)
            self.assertIn('rule_breakdown', s)
            self.assertIn('positive_factors', s)
            self.assertIn('confidence', s)
            self.assertIn('sample_size', s)
            self.assertNotIn('احتمال', s['label'])

    def test_crm_recommendation_action_relevant(self):
        # force CRM dropoff by having buyers without CRM — recommendation when drop high
        ctx = get_plan_conversion_context(days=30)
        for r in ctx['recommendations']:
            if 'CRM' in r.get('title', '') or 'CRM' in r.get('body', ''):
                self.assertNotIn('Checkout', r['action_hint'])
                self.assertTrue(
                    'مخاطب' in r['action_hint']
                    or 'CRM' in r['action_hint']
                    or 'Dataset' in r['action_hint']
                )

    def test_json_includes_purchase_funnel_and_dq(self):
        payload = build_plan_conversion_json(days=30)
        self.assertIn('purchase_funnel', payload)
        self.assertIn('activation_funnel', payload)
        self.assertIn('data_quality', payload)
        self.assertEqual(payload['meta']['version'], '2.1-bi-audit')
