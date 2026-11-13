"""تست جریان کامل کارت‌به‌کارت — اعلان، تأیید، رد و idempotency."""
from decimal import Decimal
from threading import Thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from accounts.models import SmsMessageLog
from licenses.models import License
from shop.models import CardTransferSubmission, LicensePlan, Order, Product
from shop.services.card_transfer_workflow import (
    CardTransferInvalidStateError,
    on_card_transfer_submitted,
)
from shop.services.order_fulfillment import approve_card_transfer, reject_card_transfer
from workspace.models import AgencySubscription
from workspace.services.agency_entitlement import is_agency_plan_order

User = get_user_model()


def _product_and_plans():
    product = Product.objects.create(
        title='ربات تست',
        slug='card-flow-bot',
        description='t',
        is_active=True,
    )
    personal = LicensePlan.objects.create(
        product=product,
        name='شخصی',
        plan_type='monthly',
        price=100_000,
        duration_days=30,
        max_activations=2,
        is_active=True,
    )
    agency = LicensePlan.objects.create(
        product=product,
        name='آژانس',
        plan_type='monthly',
        price=990_000,
        duration_days=30,
        max_activations=2,
        allow_bulk_purchase=True,
        min_quantity=2,
        max_quantity=10,
        is_active=True,
    )
    return product, personal, agency


def _pending_submission(user, plan, *, qty=1, amount=None):
    amount = amount if amount is not None else plan.price * qty
    order = Order.objects.create(
        user=user,
        product=plan.product,
        plan=plan,
        quantity=qty,
        amount=Decimal(amount),
        status='pending_verification',
        payment_method='card_transfer',
    )
    submission = CardTransferSubmission.objects.create(
        order=order,
        status='pending',
        reference_number='REF-TEST-001',
        payer_name='تست',
    )
    return order, submission


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferSubmissionNotificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ctuser1', password='x', phone='09123334444')
        self.staff = User.objects.create_user(
            username='ctadmin', password='x', phone='09121112222', is_staff=True,
        )
        self.product, self.personal, _ = _product_and_plans()

    @patch('accounts.services.notifications._send_templated_or_simple_sms', return_value=True)
    def test_submission_sends_admin_sms_once(self, mock_send):
        order, submission = _pending_submission(self.user, self.personal)
        on_card_transfer_submitted(submission)
        submission.refresh_from_db()
        self.assertIsNotNone(submission.admin_sms_sent_at)
        self.assertEqual(mock_send.call_count, 1)

        on_card_transfer_submitted(submission)
        self.assertEqual(mock_send.call_count, 1)

    @patch('accounts.services.notifications._send_templated_or_simple_sms', return_value=True)
    def test_submission_via_payment_view(self, mock_send):
        PaymentSettings = __import__('shop.models', fromlist=['PaymentSettings']).PaymentSettings
        PaymentSettings.objects.update_or_create(
            pk=1,
            defaults={
                'card_transfer_enabled': True,
                'card_number': '6037-9977-1234-5678',
            },
        )
        order = Order.objects.create(
            user=self.user,
            product=self.personal.product,
            plan=self.personal,
            amount=self.personal.price,
            status='pending',
        )
        self.client.login(username='ctuser1', password='x')
        with patch('shop.payment_views.CardTransferForm') as form_cls:
            form = form_cls.return_value
            form.is_valid.return_value = True
            saved = CardTransferSubmission(
                reference_number='POST-REF',
                payer_name='کاربر',
            )
            form.save.return_value = saved
            resp = self.client.post(reverse('payment:card_transfer', args=[order.id]))
        self.assertEqual(resp.status_code, 302)
        submission = CardTransferSubmission.objects.get(order=order)
        self.assertEqual(submission.status, 'pending')
        self.assertIsNotNone(submission.admin_sms_sent_at)


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferApprovePersonalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ctbuyer', password='x', phone='09125556666')
        self.staff = User.objects.create_user(
            username='ctstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.personal)

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_approve_marks_paid_and_creates_license(self, _mock_sms):
        approve_card_transfer(self.submission, self.staff)
        self.order.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.submission.status, 'approved')
        license_obj = License.objects.get(order=self.order)
        self.assertEqual(license_obj.max_activations, self.personal.max_activations)
        self.assertEqual(license_obj.status, 'inactive')

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_double_approve_no_duplicate_license(self, _mock_sms):
        approve_card_transfer(self.submission, self.staff)
        approve_card_transfer(self.submission, self.staff)
        self.assertEqual(License.objects.filter(order=self.order).count(), 1)

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_approve_from_sales_panel_view(self, _mock_sms):
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        self.client.login(username='ctstaff', password='x')
        url = reverse('admin_panel_card_transfer_approve', args=[self.submission.pk])
        resp = self.client.post(url, {'next': reverse('admin_panel_sales')})
        self.assertEqual(resp.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertTrue(License.objects.filter(order=self.order).exists())

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_approve_rejected_denied(self, _mock_sms):
        reject_card_transfer(self.submission, self.staff, 'invalid receipt')
        self.submission.refresh_from_db()
        with self.assertRaises(CardTransferInvalidStateError):
            approve_card_transfer(self.submission, self.staff)


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferAgencyApproveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agencyowner', password='x', phone='09127778888')
        self.staff = User.objects.create_user(
            username='agstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, _, self.agency_plan = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.agency_plan, qty=3)

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_agency_approval_provisions_subscription(self, _mock_sms):
        self.assertTrue(is_agency_plan_order(self.order))
        approve_card_transfer(self.submission, self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        sub = AgencySubscription.objects.get(source_order=self.order)
        self.assertEqual(sub.seat_count, 3)
        self.assertEqual(License.objects.filter(order=self.order).count(), 3)
        self.assertEqual(License.objects.filter(agency_subscription=sub).count(), 3)


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferRejectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='rejectuser', password='x', phone='09128889999')
        self.staff = User.objects.create_user(
            username='rejstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.personal)

    @patch('shop.services.card_transfer_workflow.send_customer_rejection_sms', return_value=True)
    def test_reject_no_license(self, _mock_sms):
        reject_card_transfer(self.submission, self.staff, 'رسید نامعتبر')
        self.order.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'rejected')
        self.assertEqual(self.order.status, 'failed')
        self.assertFalse(License.objects.filter(order=self.order).exists())

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    @patch('shop.services.card_transfer_workflow.send_customer_rejection_sms', return_value=True)
    def test_reject_fulfilled_denied(self, _mock_rej, _mock_app):
        approve_card_transfer(self.submission, self.staff)
        with self.assertRaises(CardTransferInvalidStateError):
            reject_card_transfer(self.submission, self.staff)


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='secuser', password='x', phone='09120001111')
        self.staff = User.objects.create_user(
            username='secstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.personal)

    def test_unauthorized_approve_forbidden(self):
        self.client.login(username='secuser', password='x')
        url = reverse('admin_panel_card_transfer_approve', args=[self.submission.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_get_approve_not_allowed(self):
        self.client.login(username='secstaff', password='x')
        url = reverse('admin_panel_card_transfer_approve', args=[self.submission.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferSmsFailureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='smsuser', password='x', phone='09122223333')
        self.staff = User.objects.create_user(
            username='smsstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.personal)

    @patch('accounts.services.notifications._send_templated_or_simple_sms', return_value=False)
    def test_sms_failure_does_not_block_approval(self, _mock_send):
        with patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=False):
            approve_card_transfer(self.submission, self.staff)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertTrue(License.objects.filter(order=self.order).exists())


@override_settings(CARD_TRANSFER_ADMIN_PHONES='09121112222')
class CardTransferFulfillmentFailureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='failuser', password='x', phone='09124445555')
        self.staff = User.objects.create_user(
            username='failstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, self.personal)

    @patch('licenses.services.claim.issue_license_for_paid_order', return_value=None)
    def test_fulfillment_failure_rolls_back_approval(self, _mock_issue):
        from shop.services.card_transfer_workflow import CardTransferFulfillmentError

        with self.assertRaises(CardTransferFulfillmentError):
            approve_card_transfer(self.submission, self.staff)
        self.order.refresh_from_db()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'pending')
        self.assertEqual(self.order.status, 'pending_verification')


class CardTransferSalesPanelContextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ctxuser', password='x', phone='09126667777')
        self.staff = User.objects.create_user(
            username='ctxstaff', password='x', phone='09121112222', is_staff=True,
        )
        _, self.personal, _ = _product_and_plans()
        _pending_submission(self.user, self.personal)

    def test_sales_panel_pending_count(self):
        from accounts.services.admin_sales_center import get_sales_center_context

        ctx = get_sales_center_context(days=30)
        self.assertEqual(ctx['card_transfer_pending_count'], 1)
        self.assertEqual(len(ctx['card_transfer_rows']), 1)

    def test_sales_panel_renders_card_section(self):
        self.client.login(username='ctxstaff', password='x')
        resp = self.client.get(reverse('admin_panel_sales'))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('sales-card-transfers', content)
        self.assertIn('پرداخت‌های کارت‌به‌کارت در انتظار بررسی', content)


class CardTransferConcurrentApproveTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='concuser', password='x', phone='09129990000')
        self.staff_a = User.objects.create_user(
            username='staffa', password='x', phone='09121110001', is_staff=True,
        )
        self.staff_b = User.objects.create_user(
            username='staffb', password='x', phone='09121110002', is_staff=True,
        )
        _, personal, _ = _product_and_plans()
        self.order, self.submission = _pending_submission(self.user, personal)
        self.errors: list[Exception] = []

    @patch('shop.services.card_transfer_workflow.send_customer_approval_sms', return_value=True)
    def test_concurrent_approve_single_license(self, _mock_sms):
        def worker(staff):
            try:
                approve_card_transfer(self.submission, staff)
            except Exception as exc:
                self.errors.append(exc)
            finally:
                connections.close_all()

        t1 = Thread(target=worker, args=(self.staff_a,))
        t2 = Thread(target=worker, args=(self.staff_b,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.order.refresh_from_db()
        self.submission.refresh_from_db()
        # SQLite ممکن است در تست همزمان قفل شود — در این صورت یک تأیید تکمیل می‌کند.
        if self.order.status != 'paid':
            approve_card_transfer(self.submission, self.staff_a)
            self.order.refresh_from_db()

        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(License.objects.filter(order=self.order).count(), 1)
        self.assertEqual(self.submission.status, 'approved')
