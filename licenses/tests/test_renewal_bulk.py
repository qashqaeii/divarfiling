"""تست تمدید چندلایسنسی و جداسازی از provisioning آژانس."""
import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from licenses.models import AuditLog, License
from licenses.services.claim import issue_licenses_for_paid_order
from licenses.services.renewal_orders import (
    create_renewal_order,
    fulfill_multi_renewal_for_paid_order,
    order_is_renewal_commerce,
    quote_renewal_order,
)
from shop.models import LicensePlan, Order, OrderRenewalItem, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import AgencySubscription, CRMAgency, CRMAgencyMember
from workspace.services.agency_entitlement import (
    get_subscription_for_agency,
    has_assigned_agency_seat,
    provision_subscription_from_paid_order,
)
from workspace.services.agency_onboarding import create_or_link_agency
from workspace.services.agency_seats import assign_seat_to_member

User = get_user_model()


def _agency_setup(qty=3):
    product = Product.objects.create(
        title='Bot Bulk',
        slug=f'bot-bulk-{uuid.uuid4().hex[:8]}',
        description='t',
        is_active=True,
        repeat_purchase_discount=10,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name='Agency',
        plan_type='monthly',
        price=500_000,
        duration_days=30,
        max_activations=2,
        allow_bulk_purchase=True,
        min_quantity=2,
        max_quantity=25,
        is_active=True,
    )
    base = int(uuid.uuid4().hex[:6], 16) % 9_000_000
    owner = User.objects.create_user(username=f'0917{base:07d}', phone=f'0917{base:07d}', password='x')
    advisor = User.objects.create_user(username=f'0917{base + 1:07d}', phone=f'0917{base + 1:07d}', password='x')
    order = Order.objects.create(
        user=owner,
        product=product,
        plan=plan,
        quantity=qty,
        amount=qty * plan.price,
        status='pending',
    )
    fulfill_order_after_payment(order)
    sub = provision_subscription_from_paid_order(order)
    agency = create_or_link_agency(owner, 'Bulk Agency')
    sub.agency = agency
    sub.save(update_fields=['agency'])
    lic = License.objects.filter(order=order, assigned_user__isnull=True).first()
    if lic:
        CRMAgencyMember.objects.create(
            agency=agency, user=advisor, role='advisor', is_active=True,
            data_visibility_consent_at=timezone.now(),
        )
        assign_seat_to_member(owner, lic.pk, advisor.pk)
    for lic in License.objects.filter(order=order):
        lic.expires_at = timezone.now() - timedelta(days=2)
        lic.status = 'expired'
        lic.save(update_fields=['expires_at', 'status'])
    sub.expires_at = timezone.now() - timedelta(days=2)
    sub.status = AgencySubscription.STATUS_EXPIRED
    sub.save(update_fields=['expires_at', 'status'])
    return owner, advisor, product, plan, order, agency, sub


class RenewalBulkTests(TestCase):
    def test_selective_renewal_only_updates_chosen_keys(self):
        owner, _, product, plan, source_order, agency, sub = _agency_setup(qty=3)
        licenses = list(License.objects.filter(order=source_order).order_by('sequence'))
        chosen = [licenses[0].pk, licenses[1].pk]
        renewal_order = create_renewal_order(
            owner, source_order.pk, license_ids=chosen, plan_id=plan.pk,
        )
        renewal_order.status = 'paid'
        renewal_order.paid_at = timezone.now()
        renewal_order.save()
        fulfill_multi_renewal_for_paid_order(renewal_order)

        licenses[0].refresh_from_db()
        licenses[1].refresh_from_db()
        licenses[2].refresh_from_db()
        sub.refresh_from_db()
        self.assertGreater(licenses[0].expires_at, timezone.now())
        self.assertGreater(licenses[1].expires_at, timezone.now())
        self.assertLess(licenses[2].expires_at, timezone.now())
        self.assertEqual(sub.status, AgencySubscription.STATUS_EXPIRED)

    def test_full_renewal_syncs_agency_subscription(self):
        owner, _, product, plan, source_order, agency, sub = _agency_setup(qty=2)
        all_ids = list(
            License.objects.filter(order=source_order).values_list('pk', flat=True)
        )
        renewal_order = create_renewal_order(
            owner, source_order.pk, license_ids=all_ids, plan_id=plan.pk,
        )
        renewal_order.status = 'paid'
        renewal_order.paid_at = timezone.now()
        renewal_order.save()
        fulfill_multi_renewal_for_paid_order(renewal_order)
        sub.refresh_from_db()
        self.assertEqual(sub.status, AgencySubscription.STATUS_ACTIVE)
        self.assertGreater(sub.expires_at, timezone.now())

    def test_renewal_order_skips_agency_provision_on_fulfill(self):
        owner, _, product, plan, source_order, agency, sub = _agency_setup(qty=2)
        old_sub_id = sub.pk
        lic_ids = [License.objects.filter(order=source_order).first().pk]
        renewal_order = create_renewal_order(
            owner, source_order.pk, license_ids=lic_ids, plan_id=plan.pk,
        )
        self.assertTrue(order_is_renewal_commerce(renewal_order))
        renewal_order.status = 'paid'
        renewal_order.paid_at = timezone.now()
        renewal_order.save()
        fulfill_order_after_payment(renewal_order)
        self.assertFalse(
            AgencySubscription.objects.filter(source_order=renewal_order).exists()
        )
        sub.refresh_from_db()
        self.assertEqual(sub.pk, old_sub_id)
        untouched = License.objects.filter(order=source_order).exclude(pk__in=lic_ids).first()
        self.assertLess(untouched.expires_at, timezone.now())

    def test_bulk_purchase_still_renews_all_prior_keys(self):
        """Regression: خرید bulk جدید همچنان کلیدهای اشتراک قبلی را تمدید می‌کند."""
        owner, _, product, plan, first_order, agency, sub = _agency_setup(qty=2)
        first_licenses = list(License.objects.filter(order=first_order))
        second_order = Order.objects.create(
            user=owner,
            product=product,
            plan=plan,
            quantity=2,
            amount=2 * plan.price,
            status='pending',
        )
        fulfill_order_after_payment(second_order)
        for lic in first_licenses:
            lic.refresh_from_db()
            self.assertGreater(lic.expires_at, timezone.now())

    def test_renewal_fulfillment_idempotent(self):
        owner, _, product, plan, source_order, _, _ = _agency_setup(qty=2)
        lic_id = License.objects.filter(order=source_order).first().pk
        renewal_order = create_renewal_order(
            owner, source_order.pk, license_ids=[lic_id], plan_id=plan.pk,
        )
        renewal_order.status = 'paid'
        renewal_order.paid_at = timezone.now()
        renewal_order.save()
        fulfill_multi_renewal_for_paid_order(renewal_order)
        lic = License.objects.get(pk=lic_id)
        first_expires = lic.expires_at
        fulfill_multi_renewal_for_paid_order(renewal_order)
        lic.refresh_from_db()
        self.assertEqual(lic.expires_at, first_expires)
        self.assertEqual(
            AuditLog.objects.filter(
                license=lic,
                details__event='license_renewed',
                details__order_id=str(renewal_order.pk),
            ).count(),
            1,
        )

    def test_advisor_entitlement_with_valid_seat_expired_subscription(self):
        owner, advisor, product, plan, source_order, agency, sub = _agency_setup(qty=2)
        lic = License.objects.filter(assigned_user=advisor).first()
        lic.expires_at = timezone.now() + timedelta(days=15)
        lic.status = 'active'
        lic.save(update_fields=['expires_at', 'status'])
        self.assertTrue(has_assigned_agency_seat(advisor))

    def test_quote_respects_bulk_tier_for_three_seats(self):
        owner, _, product, plan, source_order, _, _ = _agency_setup(qty=3)
        ids = list(License.objects.filter(order=source_order).values_list('pk', flat=True)[:3])
        quote = quote_renewal_order(owner, source_order.pk, license_ids=ids, plan_id=plan.pk)
        self.assertEqual(quote['quantity'], 3)
        self.assertGreater(quote['pricing']['discount_amount'], 0)
