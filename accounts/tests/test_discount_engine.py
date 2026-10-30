"""تست Discount Engine."""
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserDiscountIssuance
from accounts.services.discount_engine import (
    POLICY_ABANDONED_CHECKOUT,
    checkout_link_with_code,
    get_discount_policy_config,
    issue_discount,
    update_discount_policy_config,
)
from shop.models import DiscountCode

User = get_user_model()


class DiscountEngineTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='disc1', password='x', phone='09120000901')

    def test_default_policies_loaded(self):
        config = get_discount_policy_config()
        self.assertIn(POLICY_ABANDONED_CHECKOUT, config['policies'])
        self.assertEqual(config['policies'][POLICY_ABANDONED_CHECKOUT]['percent'], 10)

    def test_issue_unique_discount(self):
        result = issue_discount(
            user=self.user,
            policy_key=POLICY_ABANDONED_CHECKOUT,
            source_rule='pending_recovery_discount',
        )
        self.assertTrue(result.ok)
        self.assertTrue(result.code.startswith('DF-'))
        self.assertEqual(result.discount_percent, '10')
        self.assertEqual(UserDiscountIssuance.objects.filter(user=self.user).count(), 1)
        dc = DiscountCode.objects.get(pk=result.discount_code_id)
        self.assertEqual(dc.max_uses, 1)

    def test_reuse_active_discount(self):
        first = issue_discount(user=self.user, policy_key=POLICY_ABANDONED_CHECKOUT)
        second = issue_discount(user=self.user, policy_key=POLICY_ABANDONED_CHECKOUT)
        self.assertTrue(second.reused)
        self.assertEqual(first.code, second.code)
        self.assertEqual(UserDiscountIssuance.objects.filter(user=self.user).count(), 1)

    def test_max_codes_guardrail(self):
        issue_discount(user=self.user, policy_key=POLICY_ABANDONED_CHECKOUT)
        dc = DiscountCode.objects.filter(description__contains=f'user:{self.user.pk}').first()
        dc.valid_until = timezone.now() - timezone.timedelta(hours=1)
        dc.is_active = False
        dc.save()
        blocked = issue_discount(user=self.user, policy_key=POLICY_ABANDONED_CHECKOUT)
        self.assertFalse(blocked.ok)

    def test_checkout_link_with_uuid_order(self):
        oid = uuid.uuid4()
        link = checkout_link_with_code('DF-TEST01', order_id=oid)
        self.assertIn('code=DF-TEST01', link)
        self.assertIn(str(oid), link)

    def test_issue_discount_with_order_uuid(self):
        sample_uuid = uuid.uuid4()
        result = issue_discount(
            user=self.user,
            policy_key=POLICY_ABANDONED_CHECKOUT,
            source_rule='pending_recovery_discount',
            order_id=str(sample_uuid),
        )
        self.assertTrue(result.ok)
        self.assertIn(str(sample_uuid), result.checkout_link)

    def test_update_policy_config(self):
        update_discount_policy_config(
            policies={POLICY_ABANDONED_CHECKOUT: {'percent': 12}},
        )
        config = get_discount_policy_config()
        self.assertEqual(config['policies'][POLICY_ABANDONED_CHECKOUT]['percent'], 12)
