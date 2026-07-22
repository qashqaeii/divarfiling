"""تست تمدید لایسنس."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from licenses.models import AuditLog, License, LicenseActivation
from licenses.services.claim import issue_licenses_for_paid_order
from licenses.services.renewal import compute_renewed_expires_at, evaluate_license_renewal
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment

User = get_user_model()


def _setup_product():
    product = Product.objects.create(
        title='ربات تست',
        slug='bot-renew-test',
        description='test',
        is_active=True,
        repeat_purchase_discount=10,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name='ماهانه',
        plan_type='monthly',
        price=100000,
        duration_days=30,
        is_active=True,
    )
    return product, plan


class LicenseRenewalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='renewuser',
            password='pass1234',
            phone='09128888888',
        )
        self.product, self.plan = _setup_product()
        self.original_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        fulfill_order_after_payment(self.original_order)
        self.license = License.objects.get(order=self.original_order)
        self.license.status = 'active'
        self.license.expires_at = timezone.now() - timedelta(days=2)
        self.license.save(update_fields=['status', 'expires_at'])
        LicenseActivation.objects.create(
            license=self.license,
            hardware_fingerprint='test-hw-fingerprint-001',
            is_active=True,
        )
        self.license.sync_expiration_status(save=True)

    def test_evaluate_license_renewal_allows_expired(self):
        ok, message = evaluate_license_renewal(self.license)
        self.assertTrue(ok)
        self.assertEqual(message, '')

    def test_evaluate_license_renewal_blocks_unlimited(self):
        self.license.expires_at = None
        self.license.status = 'active'
        self.license.save(update_fields=['expires_at', 'status'])
        ok, message = evaluate_license_renewal(self.license)
        self.assertFalse(ok)
        self.assertIn('نامحدود', message)

    def test_compute_renewed_expires_from_now_when_expired(self):
        before = timezone.now()
        new_expires = compute_renewed_expires_at(self.license, self.plan)
        self.assertIsNotNone(new_expires)
        self.assertGreaterEqual(new_expires, before + timedelta(days=29))

    def test_compute_renewed_expires_stacks_when_still_active(self):
        future = timezone.now() + timedelta(days=10)
        self.license.expires_at = future
        self.license.status = 'active'
        self.license.save(update_fields=['expires_at', 'status'])
        new_expires = compute_renewed_expires_at(self.license, self.plan)
        self.assertGreaterEqual(new_expires, future + timedelta(days=29))

    def test_fulfill_renewal_extends_same_key(self):
        old_key = self.license.license_key
        renewal_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal('90000'),
            status='pending',
            renewal_license=self.license,
            quantity=1,
        )
        fulfill_order_after_payment(renewal_order)
        self.license.refresh_from_db()
        self.assertEqual(self.license.license_key, old_key)
        self.assertGreater(self.license.expires_at, timezone.now())
        self.assertEqual(self.license.status, 'active')
        self.assertTrue(
            AuditLog.objects.filter(
                license=self.license,
                details__event='license_renewed',
                details__order_id=str(renewal_order.pk),
            ).exists()
        )

    def test_fulfill_renewal_idempotent(self):
        renewal_order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
            renewal_license=self.license,
        )
        fulfill_order_after_payment(renewal_order)
        self.license.refresh_from_db()
        first_expires = self.license.expires_at
        issue_licenses_for_paid_order(renewal_order)
        self.license.refresh_from_db()
        self.assertEqual(self.license.expires_at, first_expires)
        self.assertEqual(
            AuditLog.objects.filter(
                license=self.license,
                details__event='license_renewed',
                details__order_id=str(renewal_order.pk),
            ).count(),
            1,
        )

    def test_renew_license_view_redirects_to_buy(self):
        self.client.login(username='renewuser', password='pass1234')
        url = reverse('renew_license', kwargs={'license_id': self.license.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'renew={self.license.pk}', response.url)
        self.assertIn(f'plan={self.plan.pk}', response.url)
        self.assertIn(self.product.slug, response.url)

    def test_renew_license_view_requires_owner(self):
        other = User.objects.create_user(username='other', password='pass1234', phone='09129999999')
        self.client.login(username='other', password='pass1234')
        url = reverse('renew_license', kwargs={'license_id': self.license.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_buy_page_with_renew_query_renders(self):
        self.client.login(username='renewuser', password='pass1234')
        url = reverse('buy', kwargs={'slug': self.product.slug})
        response = self.client.get(url, {'renew': self.license.pk, 'plan': self.plan.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'تمدید لایسنس')
        self.assertContains(response, self.license.license_key)
