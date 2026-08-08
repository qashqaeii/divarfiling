"""Tests for acquisition funnel audit."""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import LeadAttribution, MarketingLead
from accounts.services.acquisition_funnel_audit import audit_acquisition_funnel
from shop.models import LicensePlan, Order, Product

User = get_user_model()


class AcquisitionFunnelAuditTests(TestCase):
    def test_no_buyers_verdict_ok(self):
        MarketingLead.objects.create(
            phone_normalized='09121111111',
            status=MarketingLead.Status.ENGAGED,
        )
        report = audit_acquisition_funnel(sample_limit=5)
        self.assertEqual(report['verdict'], 'ok')
        self.assertEqual(report['ground_truth']['leads_with_paid_order_by_phone_or_user'], 0)
        self.assertEqual(report['dashboard']['total_purchases_ui'], 0)

    def test_buyer_gets_conversion_after_attribute_purchase(self):
        user = User.objects.create_user(username='buyer1', password='x', phone='09122222222')
        MarketingLead.objects.create(
            phone_normalized='09122222222',
            status=MarketingLead.Status.REGISTERED,
            matched_user=user,
        )
        product = Product.objects.create(title='ربات', slug='bot-audit-test', is_active=True)
        plan = LicensePlan.objects.create(
            product=product,
            name='یک هفته',
            plan_type='daily',
            price=Decimal('50000'),
        )
        Order.objects.create(
            user=user,
            product=product,
            plan=plan,
            amount=Decimal('50000'),
            status='paid',
        )
        order = Order.objects.filter(user=user, status='paid').first()
        from accounts.services.lead_attribution import attribute_purchase

        attribute_purchase(order=order)

        report = audit_acquisition_funnel(sample_limit=5)
        self.assertEqual(report['ground_truth']['leads_with_paid_order_by_phone_or_user'], 1)
        self.assertGreaterEqual(
            LeadAttribution.objects.filter(
                axis=LeadAttribution.Axis.CONVERSION,
                touch_model=LeadAttribution.TouchModel.LAST,
            ).count(),
            1,
        )
        self.assertIn(report['verdict'], ('ok', 'review'))
        self.assertEqual(report['dashboard']['total_purchases_ui'], 1)
