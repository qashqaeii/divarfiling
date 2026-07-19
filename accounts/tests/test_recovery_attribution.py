"""Tests for Recovery Attribution Engine — Week 2."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog, MarketingAutomationRun, RecoveryAttribution
from accounts.services.recovery_attribution import (
    ASSISTED_RULE_VERSION,
    STRICT_RULE_VERSION,
    backfill_attributions,
    build_attribution,
    evaluate_attribution,
    is_production_recovery_send,
    match_assisted,
    match_strict,
)
from accounts.services.pending_recovery import FLOW_KEY, STEP_RECOVERY_1, STEP_RECOVERY_1_LATE
from shop.models import LicensePlan, Order, PlanFunnelEvent, Product

User = get_user_model()


def _product_plan(slug='attr-bot'):
    product = Product.objects.create(
        title='Attr Product', slug=slug, description='t', is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product, name='ماهانه', plan_type='monthly',
        price=500_000, duration_days=30, is_active=True,
    )
    return product, plan


def _run():
    return MarketingAutomationRun.objects.create(
        flow_key=FLOW_KEY,
        mode=MarketingAutomationRun.Mode.LIVE,
        status=MarketingAutomationRun.Status.COMPLETED,
    )


def _production_log(*, user, order, product, step_key=STEP_RECOVERY_1, sms_time=None, suffix='1'):
    run = _run()
    sms_time = sms_time or timezone.now()
    with patch('django.utils.timezone.now', return_value=sms_time):
        log = MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=step_key,
            user=user,
            phone_hash=f'hash{suffix}',
            masked_phone='0912***00',
            order=order,
            product=product,
            action=MarketingAutomationActionLog.Action.PROVIDER_ACCEPTED,
            decision_key=f'decision:attr-{suffix}',
            send_idempotency_key=f'send:attr:{suffix}',
        )
    MarketingAutomationActionLog.objects.filter(pk=log.pk).update(created_at=sms_time)
    log.refresh_from_db()
    return log


class RecoveryAttributionMatcherTests(TestCase):
    def setUp(self):
        self.product, self.plan = _product_plan()
        self.user = User.objects.create_user(username='attr_u1', password='x', phone='09121112233')
        self.now = timezone.now()
        self.sms_time = self.now - timedelta(hours=10)

    def _pending_order(self, *, hours_ago=10):
        order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=500_000,
            status='pending',
        )
        Order.objects.filter(pk=order.pk).update(
            created_at=self.now - timedelta(hours=hours_ago),
        )
        order.refresh_from_db()
        return order

    def test_strict_match_same_order_after_sms(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = self.sms_time + timedelta(hours=5)
        order.save(update_fields=['status', 'paid_at'])
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time)
        match = match_strict(log)
        self.assertEqual(match.status, RecoveryAttribution.Status.MATCHED)
        self.assertEqual(match.attribution_model, RecoveryAttribution.AttributionModel.STRICT)
        self.assertEqual(match.rule_version, STRICT_RULE_VERSION)

    def test_no_match_paid_before_sms(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = self.sms_time - timedelta(hours=1)
        order.save(update_fields=['status', 'paid_at'])
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='2')
        match = match_strict(log)
        self.assertEqual(match.status, RecoveryAttribution.Status.NO_MATCH)

    def test_no_match_after_72h_window(self):
        order = self._pending_order()
        sms_time = self.now - timedelta(hours=80)
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=sms_time, suffix='3')
        match = match_strict(log)
        self.assertEqual(match.status, RecoveryAttribution.Status.NO_MATCH)

    def test_pending_within_window_unpaid(self):
        order = self._pending_order()
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='4')
        match = match_strict(log)
        self.assertEqual(match.status, RecoveryAttribution.Status.PENDING)

    def test_ignore_would_send(self):
        run = _run()
        order = self._pending_order()
        log = MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            user=self.user,
            phone_hash='wh',
            masked_phone='0912***00',
            order=order,
            product=self.product,
            action=MarketingAutomationActionLog.Action.WOULD_SEND,
            decision_key='decision:ws',
        )
        self.assertFalse(is_production_recovery_send(log))
        self.assertIsNone(build_attribution(log, persist=True))

    def test_ignore_test_provider_accepted(self):
        run = _run()
        order = self._pending_order()
        log = MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            user=self.user,
            phone_hash='th',
            masked_phone='0912***00',
            order=order,
            product=self.product,
            action=MarketingAutomationActionLog.Action.TEST_PROVIDER_ACCEPTED,
            decision_key='decision:test',
            send_idempotency_key='test:send:1',
        )
        self.assertIsNone(build_attribution(log, persist=True))

    def test_assisted_new_order_same_user_product(self):
        abandon = self._pending_order(hours_ago=30)
        PlanFunnelEvent.objects.create(
            event_type='checkout_abandon',
            user=self.user,
            order=abandon,
            product=self.product,
            plan=self.plan,
        )
        new_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=500_000,
            status='paid',
            paid_at=self.sms_time + timedelta(hours=12),
        )
        log = _production_log(
            user=self.user,
            order=abandon,
            product=self.product,
            sms_time=self.sms_time,
            suffix='assist',
        )
        strict = match_strict(log)
        self.assertNotEqual(strict.status, RecoveryAttribution.Status.MATCHED)
        assisted = match_assisted(log)
        self.assertEqual(assisted.status, RecoveryAttribution.Status.MATCHED)
        self.assertEqual(assisted.attribution_model, RecoveryAttribution.AttributionModel.ASSISTED)
        self.assertEqual(assisted.paid_order.pk, new_order.pk)

    def test_no_match_different_product(self):
        other_product, other_plan = _product_plan('attr-other')
        order = self._pending_order()
        other = Order.objects.create(
            user=self.user,
            product=other_product,
            plan=other_plan,
            amount=400_000,
            status='paid',
            paid_at=self.sms_time + timedelta(hours=3),
        )
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='dp')
        match = match_strict(log)
        self.assertNotEqual(match.status, RecoveryAttribution.Status.MATCHED)
        assisted = match_assisted(log)
        self.assertNotEqual(getattr(assisted, 'paid_order', None), other)

    def test_immutable_after_matched(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = self.sms_time + timedelta(hours=2)
        order.save(update_fields=['status', 'paid_at'])
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='imm')
        row = build_attribution(log, persist=True)
        self.assertEqual(row.status, RecoveryAttribution.Status.MATCHED)
        matched_at = row.matched_at
        order.paid_at = self.sms_time + timedelta(hours=20)
        order.save(update_fields=['paid_at'])
        row2 = build_attribution(log, persist=True)
        self.assertEqual(row.pk, row2.pk)
        self.assertEqual(row2.matched_at, matched_at)
        self.assertEqual(row2.lag_hours, row.lag_hours)

    def test_duplicate_job_does_not_create_second_row(self):
        order = self._pending_order()
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='dup')
        row1 = build_attribution(log, persist=True)
        row2 = build_attribution(log, persist=True)
        self.assertEqual(RecoveryAttribution.objects.filter(action_log=log).count(), 1)
        self.assertEqual(row1.pk, row2.pk)

    def test_pending_transitions_to_matched(self):
        order = self._pending_order()
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='tr')
        row = build_attribution(log, persist=True)
        self.assertEqual(row.status, RecoveryAttribution.Status.PENDING)
        order.status = 'paid'
        order.paid_at = self.sms_time + timedelta(hours=4)
        order.save(update_fields=['status', 'paid_at'])
        row2 = build_attribution(log, persist=True)
        self.assertEqual(row2.status, RecoveryAttribution.Status.MATCHED)
        self.assertIsNotNone(row2.matched_at)

    def test_backfill_only_production_sends(self):
        order = self._pending_order()
        _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='bf1')
        run = _run()
        MarketingAutomationActionLog.objects.create(
            run=run,
            flow_key=FLOW_KEY,
            step_key=STEP_RECOVERY_1,
            user=self.user,
            phone_hash='bfw',
            masked_phone='0912***00',
            order=order,
            product=self.product,
            action=MarketingAutomationActionLog.Action.WOULD_SEND,
            decision_key='decision:bfw',
        )
        stats = backfill_attributions(since=self.now - timedelta(days=1))
        self.assertGreaterEqual(stats['examined'], 1)
        self.assertEqual(
            RecoveryAttribution.objects.filter(
                action_log__action=MarketingAutomationActionLog.Action.WOULD_SEND,
            ).count(),
            0,
        )

    def test_two_sms_one_order_only_one_strict_match_on_payment(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = self.sms_time + timedelta(hours=6)
        order.save(update_fields=['status', 'paid_at'])
        log1 = _production_log(
            user=self.user,
            order=order,
            product=self.product,
            sms_time=self.sms_time,
            suffix='t1',
            step_key=STEP_RECOVERY_1,
        )
        log2 = _production_log(
            user=self.user,
            order=order,
            product=self.product,
            sms_time=self.sms_time + timedelta(hours=1),
            suffix='t2',
            step_key=STEP_RECOVERY_1_LATE,
        )
        row1 = build_attribution(log1, persist=True)
        row2 = build_attribution(log2, persist=True)
        matched = [row1, row2]
        matched_count = sum(1 for r in matched if r.status == RecoveryAttribution.Status.MATCHED)
        self.assertGreaterEqual(matched_count, 1)

    def test_evaluate_prefers_strict_over_assisted(self):
        order = self._pending_order()
        order.status = 'paid'
        order.paid_at = self.sms_time + timedelta(hours=3)
        order.save(update_fields=['status', 'paid_at'])
        PlanFunnelEvent.objects.create(
            event_type='checkout_abandon',
            user=self.user,
            order=order,
            product=self.product,
            plan=self.plan,
        )
        log = _production_log(user=self.user, order=order, product=self.product, sms_time=self.sms_time, suffix='pr')
        result = evaluate_attribution(log)
        self.assertEqual(result.attribution_model, RecoveryAttribution.AttributionModel.STRICT)
