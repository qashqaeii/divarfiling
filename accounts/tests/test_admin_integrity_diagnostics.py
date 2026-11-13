"""Phase 01C: read-only integrity diagnostics and scoped user dossiers."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.services.admin_action_permissions import (
    can_view_financial_integrity,
    can_view_user_management,
)
from accounts.services.admin_integrity_diagnostics import (
    financial_integrity_querysets,
    get_financial_integrity_context,
)
from licenses.models import License
from shop.models import LicensePlan, Order, OrderRenewalItem, Product, Transaction

User = get_user_model()


class AdminUserDossierPermissionsTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='dossier_staff', phone='09127881101', is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='dossier_owner', phone='09127881102', is_staff=True,
            is_superuser=True,
        )
        self.customer = User.objects.create_user(
            username='dossier_customer', phone='09127881103',
        )

    def grant(self, *perms):
        for app_label, codename in perms:
            permission = Permission.objects.get(
                content_type__app_label=app_label, codename=codename,
            )
            self.staff.user_permissions.add(permission)

    def test_staff_without_roles_cannot_use_personal_json_endpoints(self):
        self.client.force_login(self.staff)
        with patch('accounts.admin_views.list_users_management') as list_users:
            result = self.client.get(reverse('admin_panel_users_json'))
        self.assertEqual(result.status_code, 403)
        list_users.assert_not_called()

        with patch('accounts.admin_views.get_user_management_detail') as detail:
            result = self.client.get(
                reverse('admin_panel_user_detail_json', args=[self.customer.pk])
            )
        self.assertEqual(result.status_code, 403)
        detail.assert_not_called()

    def test_all_three_view_permissions_required_for_full_dossier(self):
        self.assertFalse(can_view_user_management(self.staff))
        self.grant(('accounts', 'view_user'))
        self.assertFalse(can_view_user_management(self.staff))
        self.grant(('shop', 'view_order'))
        self.assertFalse(can_view_user_management(self.staff))
        self.grant(('licenses', 'view_license'))
        self.assertTrue(can_view_user_management(self.staff))
        self.assertTrue(can_view_user_management(self.owner))
        self.assertFalse(can_view_user_management(self.customer))

    def test_authorized_endpoints_are_nocache_and_return_data(self):
        self.client.force_login(self.owner)
        list_response = self.client.get(
            reverse('admin_panel_users_json'), {'q': '09127881103'}
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response['Cache-Control'], 'private, no-store')
        self.assertTrue(list_response.json()['ok'])

        detail_response = self.client.get(
            reverse('admin_panel_user_detail_json', args=[self.customer.pk])
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response['Cache-Control'], 'private, no-store')
        self.assertEqual(detail_response.json()['user']['id'], self.customer.pk)

    def test_plain_staff_gets_aggregate_dashboard_without_personal_table(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_panel_users'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chart-signups')
        self.assertContains(response, 'id="ecc-users-mgmt"')
        self.assertContains(response, 'پرونده فردی کاربران')
        self.assertNotContains(response, 'data-users-list-url=')
        self.assertNotContains(response, 'id="eccUserDrawer"')
        self.assertNotContains(response, self.customer.phone)

    def test_financial_diagnostics_have_separate_read_role(self):
        self.assertFalse(can_view_financial_integrity(self.staff))
        self.grant(('shop', 'view_order'))
        self.assertFalse(can_view_financial_integrity(self.staff))
        self.grant(('licenses', 'view_license'))
        self.assertFalse(can_view_financial_integrity(self.staff))
        self.grant(('accounts', 'view_user'))
        self.assertTrue(can_view_financial_integrity(self.staff))

    def test_plain_staff_cannot_view_sales_integrity_preview(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('admin_panel_sales'), {'audit': 'complete_without_license'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="sales-integrity"')


class SalesFinancialIntegrityQueryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='integrity_owner', phone='09127881104',
            is_staff=True, is_superuser=True,
        )
        self.buyer = User.objects.create_user(
            username='integrity_buyer', phone='09127881105',
        )
        self.product = Product.objects.create(
            title='Audit product', slug='audit-product', is_active=True,
        )
        self.plan = LicensePlan.objects.create(
            product=self.product, name='Monthly', plan_type='monthly',
            price=100000, duration_days=30, is_active=True,
        )
        self.now = timezone.now()

    def order(self, **overrides):
        data = {
            'user': self.buyer,
            'product': self.product,
            'plan': self.plan,
            'amount': Decimal('100000'),
            'status': 'paid',
            'paid_at': self.now,
            'fulfillment_status': Order.FulfillmentStatus.COMPLETE,
        }
        data.update(overrides)
        return Order.objects.create(**data)

    def test_diagnostics_find_four_independent_read_only_exception_types(self):
        missing_date = self.order(paid_at=None)
        missing_license = self.order()
        under_issued = self.order(quantity=3)
        License.objects.create(
            order=under_issued, plan=self.plan,
            license_key='AUDIT-UNDER-ISSUED-KEY',
        )
        incomplete = self.order(fulfillment_status=Order.FulfillmentStatus.PARTIAL)
        gateway = self.order(status='pending', paid_at=None)
        Transaction.objects.create(
            order=gateway, status='paid',
            zibal_track_id='ZIBAL-AUDIT', amount=gateway.amount,
        )
        # Genuine issued new-key order is healthy even if paid.
        healthy = self.order()
        License.objects.create(
            order=healthy, plan=self.plan, license_key='AUDIT-HEALTHY-KEY',
        )
        # A multi-license renewal has no new license issued on its renewal
        # order; its existing license was renewed, so it is not a missing key.
        renewed = self.order()
        old_license = License.objects.get(order=healthy)
        OrderRenewalItem.objects.create(
            order=renewed, license=old_license,
            unit_original_price=Decimal('100000'),
            unit_final_price=Decimal('100000'),
        )

        cohorts = financial_integrity_querysets()
        self.assertEqual(cohorts['paid_missing_date'].count(), 1)
        self.assertEqual(cohorts['complete_without_license'].count(), 3)
        self.assertEqual(cohorts['gateway_paid_order_unpaid'].count(), 1)
        self.assertEqual(cohorts['fulfillment_incomplete'].count(), 1)

        results = get_financial_integrity_context(selected='complete_without_license', limit=1)
        self.assertEqual(len(results['rows']), 1)
        self.assertTrue(results['active_issue'])
        self.assertEqual(results['selected'], 'complete_without_license')
        self.assertEqual(missing_license.status, 'paid')
        self.assertEqual(under_issued.quantity, 3)
        self.assertEqual(missing_date.fulfillment_status, Order.FulfillmentStatus.COMPLETE)
        self.assertEqual(incomplete.fulfillment_status, Order.FulfillmentStatus.PARTIAL)

    def test_card_transfer_does_not_create_false_zibal_mismatch(self):
        card = self.order(status='pending', payment_method='card_transfer')
        Transaction.objects.create(
            order=card, status='paid', zibal_track_id='CARD-RECORD',
            amount=card.amount,
        )
        self.assertEqual(
            financial_integrity_querysets()['gateway_paid_order_unpaid'].count(), 0
        )

    def test_unknown_filter_does_not_return_raw_orders(self):
        self.order()
        ctx = get_financial_integrity_context(selected='unrecognized', limit=500)
        self.assertEqual(ctx['selected'], '')
        self.assertEqual(ctx['rows'], [])

    def test_owner_can_open_selected_bounded_preview_without_mutation(self):
        target = self.order()
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse('admin_panel_sales'), {'days': '7', 'audit': 'complete_without_license'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="sales-integrity"')
        self.assertContains(response, 'id="sales-integrity-results"')
        self.assertContains(response, 'ممیزی صرفاً خواندنی')
        target.refresh_from_db()
        self.assertEqual(target.status, 'paid')
        self.assertEqual(target.fulfillment_status, Order.FulfillmentStatus.COMPLETE)
        self.assertFalse(License.objects.filter(order=target).exists())
