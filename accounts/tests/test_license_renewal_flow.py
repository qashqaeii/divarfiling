"""تست اتوماسیون تمدید لایسنس (marketing license_renewal)."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import MarketingAutomationActionLog
from accounts.services.license_renewal import run_license_renewal
from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment

User = get_user_model()


@override_settings(LICENSE_RENEWAL_FLOW_ENABLED=True, LICENSE_RENEWAL_WITHIN_DAYS=7)
class LicenseRenewalFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='licrenflow',
            password='pass1234',
            phone='09121112233',
        )
        product = Product.objects.create(
            title='ربات تست تمدید',
            slug='bot-licren-flow',
            description='test',
            is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product,
            name='ماهانه',
            plan_type='monthly',
            price=100000,
            duration_days=30,
            is_active=True,
        )
        order = Order.objects.create(
            user=self.user,
            product=product,
            plan=plan,
            amount=plan.price,
            status='pending',
        )
        fulfill_order_after_payment(order)
        self.license = License.objects.get(order=order)
        self.license.status = 'active'
        self.license.expires_at = timezone.now() + timedelta(days=3)
        self.license.save(update_fields=['status', 'expires_at'])

    @patch('accounts.services.license_renewal.is_send_allowed', return_value=True)
    def test_dry_run_twice_same_day_does_not_break(self, _allowed):
        first = run_license_renewal(dry_run=True, live=False, limit=10)
        second = run_license_renewal(dry_run=True, live=False, limit=10)

        self.assertTrue(first.get('ok'))
        self.assertTrue(second.get('ok'))
        self.assertGreaterEqual(first['would_send'], 1)
        self.assertGreaterEqual(second['would_send'], 1)
        self.assertEqual(
            MarketingAutomationActionLog.objects.filter(
                flow_key='license_renewal',
                action=MarketingAutomationActionLog.Action.WOULD_SEND,
            ).count(),
            2,
        )
        # Decision keys must be run-scoped (no UniqueViolation across dry runs).
        keys = list(
            MarketingAutomationActionLog.objects.filter(flow_key='license_renewal')
            .values_list('decision_key', flat=True)
        )
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(k.startswith(f'dry:{first["run_id"]}:') or k.startswith(f'dry:{second["run_id"]}:') for k in keys))
