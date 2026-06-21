"""تست‌های پرداخت و تکمیل سفارش."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from shop.models import LicensePlan, Order, PaymentSettings, Product, Transaction
from shop.services.order_fulfillment import fulfill_order_after_payment
from shop.services.zibal import ZibalRequestResult, ZibalVerifyResult

User = get_user_model()


def _setup_payment_product():
    product = Product.objects.create(
        title='ربات',
        slug='bot-payment-test',
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
    return product, plan


def _enable_zibal():
    PaymentSettings.objects.update_or_create(
        pk=1,
        defaults={'zibal_enabled': True, 'card_transfer_enabled': False, 'card_number': ''},
    )


class PaymentFulfillmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer1',
            password='pass1234',
            phone='09126666666',
        )
        self.product, self.plan = _setup_payment_product()
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )

    def test_fulfill_marks_order_paid(self):
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNotNone(self.order.paid_at)

    def test_fulfill_idempotent_on_double_callback(self):
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        first_paid_at = self.order.paid_at
        fulfill_order_after_payment(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.order.paid_at, first_paid_at)


@override_settings(ZIBAL_MERCHANT_ID='')
class ZibalMerchantValidationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer2',
            password='pass1234',
            phone='09127777777',
        )
        self.product, self.plan = _setup_payment_product()
        self.product.slug = 'bot-zibal-test'
        self.product.save(update_fields=['slug'])
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=self.plan.price,
            status='pending',
        )
        _enable_zibal()

    def test_checkout_shows_configuration_warning(self):
        self.client.login(username='payer2', password='pass1234')
        resp = self.client.get(reverse('payment:checkout', args=[self.order.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'درگاه هنوز پیکربندی نشده')

    def test_initiate_without_merchant_redirects_with_error(self):
        self.client.login(username='payer2', password='pass1234')
        resp = self.client.post(reverse('payment:initiate', args=[self.order.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/payment/checkout/', resp.url)


@override_settings(
    ZIBAL_MERCHANT_ID='zibal',
    ZIBAL_REQUEST_URL='https://gateway.zibal.ir/v1/request',
    ZIBAL_VERIFY_URL='https://gateway.zibal.ir/v1/verify',
    ZIBAL_START_PAY_URL='https://gateway.zibal.ir/start/',
)
class ZibalPaymentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer3',
            password='pass1234',
            phone='09128888888',
        )
        self.product, self.plan = _setup_payment_product()
        self.order = Order.objects.create(
            user=self.user,
            product=self.product,
            plan=self.plan,
            amount=Decimal('150000'),
            status='pending',
        )
        _enable_zibal()
        self.client.login(username='payer3', password='pass1234')

    @patch('shop.payment_views.zibal_service.request_payment')
    def test_initiate_creates_transaction_and_redirect_page(self, mock_request):
        mock_request.return_value = ZibalRequestResult(
            track_id='999888777',
            result_code=100,
            message='success',
            raw={'result': 100, 'trackId': '999888777'},
        )
        resp = self.client.post(reverse('payment:initiate', args=[self.order.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '999888777')
        self.assertContains(resp, 'gateway.zibal.ir/start/999888777')
        self.order.refresh_from_db()
        self.assertEqual(self.order.zibal_track_id, '999888777')
        transaction = Transaction.objects.get(order=self.order)
        self.assertEqual(transaction.status, 'pending')
        self.assertEqual(transaction.zibal_track_id, '999888777')

    @patch('shop.payment_views.zibal_service.verify_payment')
    def test_callback_success_fulfills_order(self, mock_verify):
        Transaction.objects.create(
            order=self.order,
            zibal_track_id='555444333',
            amount=self.order.amount,
            status='pending',
        )
        self.order.zibal_track_id = '555444333'
        self.order.save(update_fields=['zibal_track_id'])

        mock_verify.return_value = ZibalVerifyResult(
            result_code=100,
            message='verified',
            ref_number='REF123456',
            paid_amount_rial=1500000,
            card_number='6037-****-****-1234',
            raw={'result': 100, 'refNumber': 'REF123456', 'amount': 1500000},
        )

        resp = self.client.get(
            reverse('payment:callback'),
            {'trackId': '555444333', 'success': '1', 'status': '2', 'orderId': str(self.order.id)},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/payment/success/', resp.url)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        transaction = Transaction.objects.get(order=self.order)
        self.assertEqual(transaction.status, 'paid')
        self.assertEqual(transaction.zibal_ref_number, 'REF123456')
        self.assertEqual(transaction.paid_amount_rial, 1500000)

    @patch('shop.payment_views.zibal_service.verify_payment')
    def test_callback_idempotent_when_order_already_paid(self, mock_verify):
        Transaction.objects.create(
            order=self.order,
            zibal_track_id='111222333',
            amount=self.order.amount,
            status='paid',
            verified_at=timezone.now(),
        )
        self.order.status = 'paid'
        self.order.paid_at = timezone.now()
        self.order.zibal_track_id = '111222333'
        self.order.save()

        resp = self.client.get(
            reverse('payment:callback'),
            {'trackId': '111222333', 'success': '1', 'status': '2'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/payment/success/', resp.url)
        mock_verify.assert_not_called()

    def test_callback_cancelled_marks_order_failed(self):
        Transaction.objects.create(
            order=self.order,
            zibal_track_id='777666555',
            amount=self.order.amount,
            status='pending',
        )
        resp = self.client.get(
            reverse('payment:callback'),
            {'trackId': '777666555', 'success': '0', 'status': '3'},
        )
        self.assertRedirects(resp, reverse('payment:failed'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'failed')
        transaction = Transaction.objects.get(order=self.order)
        self.assertEqual(transaction.status, 'cancelled')

    def test_buy_redirects_to_checkout_for_zibal(self):
        resp = self.client.post(
            reverse('buy', kwargs={'slug': self.product.slug}),
            {'plan': self.plan.pk, 'payment_method': 'zibal'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/payment/checkout/', resp.url)
