"""
ویوهای پرداخت — درگاه زیبال و کارت به کارت
"""
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Order, Transaction, PaymentSettings, CardTransferSubmission, PaymentWebhookLog
from .payment_forms import CardTransferForm
from .services.order_fulfillment import fulfill_order_after_payment
from .services.downloads import (
    build_download_response,
    get_order_download_filename,
    log_download,
    order_can_download,
)
from .services import zibal as zibal_service
from licenses.models import License

logger = logging.getLogger(__name__)


class PaymentConfigurationError(Exception):
    """تنظیمات درگاه پرداخت ناقص است."""


def _payment_settings():
    return PaymentSettings.load()


def _get_payable_order(request, order_id) -> Order:
    return get_object_or_404(Order, id=order_id, user=request.user)


def _guard_order_plan_requirements(request, order):
    from shop.services.plan_guards import (
        BLOCK_PHONE_VERIFY,
        evaluate_plan_purchase,
        verify_phone_redirect_url,
    )

    ok, message, reason = evaluate_plan_purchase(request.user, order.plan)
    if ok:
        return None
    messages.error(request, message)
    buy_url = reverse('buy', kwargs={'slug': order.product.slug})
    if reason == BLOCK_PHONE_VERIFY:
        next_url = f'{buy_url}?plan={order.plan_id}'
        return redirect(verify_phone_redirect_url(next_url))
    return redirect(buy_url)


def _order_ready_for_online_payment(order: Order) -> bool:
    return order.status in ('pending', 'failed')


def _reset_order_for_retry(order: Order) -> None:
    if order.status == 'failed':
        order.status = 'pending'
        order.save(update_fields=['status'])


def _log_callback(request, payload: dict) -> None:
    try:
        PaymentWebhookLog.objects.create(
            payload=payload,
            headers={
                key: value
                for key, value in request.META.items()
                if key.startswith('HTTP_') or key in ('REMOTE_ADDR', 'QUERY_STRING')
            },
            ip_address=request.META.get('REMOTE_ADDR'),
        )
    except Exception:
        logger.exception('Failed to persist payment callback log')


def _create_or_update_pending_transaction(order: Order, track_id: str, request_result) -> Transaction:
    transaction, _ = Transaction.objects.update_or_create(
        order=order,
        defaults={
            'zibal_track_id': track_id,
            'amount': order.amount,
            'status': 'pending',
            'gateway_result_code': request_result.result_code,
            'gateway_message': request_result.message,
            'verify_payload': request_result.raw,
        },
    )
    order.zibal_track_id = track_id
    order.payment_method = 'zibal'
    order.save(update_fields=['zibal_track_id', 'payment_method'])
    return transaction


def _finalize_successful_payment(order: Order, transaction: Transaction, verify_result) -> None:
    fulfill_order_after_payment(order)
    transaction.status = 'paid'
    transaction.zibal_ref_number = verify_result.ref_number
    transaction.gateway_result_code = verify_result.result_code
    transaction.gateway_message = verify_result.message
    transaction.verify_payload = verify_result.raw
    transaction.paid_amount_rial = verify_result.paid_amount_rial
    transaction.card_number_masked = verify_result.card_number
    transaction.verified_at = timezone.now()
    transaction.save()


class PaymentCheckoutView(LoginRequiredMixin, View):
    """مرور نهایی سفارش قبل از انتقال به درگاه زیبال"""

    template_name = 'shop/payment_checkout.html'

    def get(self, request, order_id):
        order = _get_payable_order(request, order_id)
        blocked = _guard_order_plan_requirements(request, order)
        if blocked:
            return blocked
        pay_settings = _payment_settings()

        if order.status == 'paid':
            return redirect('payment:success', order_id=order.id)

        if order.status == 'pending_verification':
            return redirect('payment:card_pending', order_id=order.id)

        if order.payment_method == 'card_transfer':
            return redirect('payment:card_transfer', order_id=order.id)

        if not pay_settings.zibal_enabled:
            if pay_settings.card_transfer_enabled and pay_settings.card_number.strip():
                order.payment_method = 'card_transfer'
                order.save(update_fields=['payment_method'])
                return redirect('payment:card_transfer', order_id=order.id)
            messages.error(request, 'در حال حاضر روش پرداخت آنلاین فعال نیست.')
            return redirect('buy', slug=order.product.slug)

        if not _order_ready_for_online_payment(order):
            messages.error(request, 'این سفارش قابل پرداخت نیست.')
            return redirect('dashboard')

        try:
            zibal_service.get_merchant_id()
            merchant_configured = True
        except zibal_service.ZibalConfigurationError:
            merchant_configured = False

        context = {
            'order': order,
            'pay_settings': pay_settings,
            'merchant_configured': merchant_configured,
            'amount_rial': zibal_service.toman_to_rial(order.amount),
        }
        return render(request, self.template_name, context)


class PaymentInitiateView(LoginRequiredMixin, View):
    """ثبت تراکنش در زیبال و انتقال به درگاه"""

    def post(self, request, order_id):
        return self._initiate(request, order_id)

    def get(self, request, order_id):
        return self._initiate(request, order_id)

    def _initiate(self, request, order_id):
        order = _get_payable_order(request, order_id)
        blocked = _guard_order_plan_requirements(request, order)
        if blocked:
            return blocked
        pay_settings = _payment_settings()

        if order.status == 'paid':
            messages.info(request, 'این سفارش قبلاً پرداخت شده است.')
            return redirect('payment:success', order_id=order.id)

        if order.status == 'pending_verification':
            return redirect('payment:card_pending', order_id=order.id)

        if not pay_settings.zibal_enabled:
            messages.error(request, 'در حال حاضر روش پرداخت آنلاین فعال نیست.')
            return redirect('payment:checkout', order_id=order.id)

        if not _order_ready_for_online_payment(order):
            messages.error(request, 'این سفارش قابل پرداخت نیست.')
            return redirect('dashboard')

        _reset_order_for_retry(order)

        try:
            callback_url = zibal_service.build_callback_url(request)
            mobile = getattr(order.user, 'phone', '') or ''
            request_result = zibal_service.request_payment(
                order=order,
                callback_url=callback_url,
                mobile=mobile,
            )
        except zibal_service.ZibalConfigurationError:
            messages.error(
                request,
                'درگاه پرداخت هنوز پیکربندی نشده است. کد مرچنت زیبال را در فایل .env قرار دهید.',
            )
            return redirect('payment:checkout', order_id=order.id)
        except zibal_service.ZibalAPIError as exc:
            messages.error(request, exc.message)
            return redirect('payment:checkout', order_id=order.id)
        except Exception:
            logger.exception('Zibal request failed for order %s', order.id)
            messages.error(request, 'خطا در ارتباط با درگاه پرداخت. لطفاً دوباره تلاش کنید.')
            return redirect('payment:checkout', order_id=order.id)

        _create_or_update_pending_transaction(order, request_result.track_id, request_result)
        pay_url = zibal_service.get_start_pay_url(request_result.track_id)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'redirect_url': pay_url})

        return render(
            request,
            'shop/payment_redirect.html',
            {
                'order': order,
                'pay_url': pay_url,
                'track_id': request_result.track_id,
            },
        )


class CardTransferView(LoginRequiredMixin, View):
    """صفحه پرداخت کارت به کارت و ثبت رسید"""
    template_name = 'shop/card_transfer.html'

    def _get_order(self, request, order_id):
        return get_object_or_404(Order, id=order_id, user=request.user)

    def get(self, request, order_id):
        order = self._get_order(request, order_id)
        blocked = _guard_order_plan_requirements(request, order)
        if blocked:
            return blocked
        pay_settings = _payment_settings()

        if order.status == 'paid':
            return redirect('payment:success', order_id=order.id)

        if order.status == 'pending_verification':
            return redirect('payment:card_pending', order_id=order.id)

        if order.status not in ('pending',):
            messages.error(request, 'این سفارش قابل پرداخت نیست.')
            return redirect('dashboard')

        if not pay_settings.card_transfer_enabled or not pay_settings.card_number.strip():
            messages.error(request, 'پرداخت کارت به کارت در حال حاضر فعال نیست.')
            return redirect('payment:checkout', order_id=order.id)

        context = {
            'order': order,
            'pay_settings': pay_settings,
            'form': CardTransferForm(),
        }
        return render(request, self.template_name, context)

    def post(self, request, order_id):
        order = self._get_order(request, order_id)
        blocked = _guard_order_plan_requirements(request, order)
        if blocked:
            return blocked
        pay_settings = _payment_settings()

        if order.status == 'pending_verification':
            return redirect('payment:card_pending', order_id=order.id)

        if not pay_settings.card_transfer_enabled:
            messages.error(request, 'پرداخت کارت به کارت غیرفعال است.')
            return redirect('buy', slug=order.product.slug)

        form = CardTransferForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {
                'order': order,
                'pay_settings': pay_settings,
                'form': form,
            })

        submission = form.save(commit=False)
        submission.order = order
        submission.status = 'pending'
        submission.save()

        order.payment_method = 'card_transfer'
        order.status = 'pending_verification'
        order.save(update_fields=['payment_method', 'status'])

        messages.success(
            request,
            'درخواست شما ثبت شد. پس از بررسی توسط پشتیبانی، لایسنس فعال می‌شود.',
        )
        return redirect('payment:card_pending', order_id=order.id)


class CardTransferPendingView(LoginRequiredMixin, TemplateView):
    """صفحه انتظار تایید کارت به کارت"""
    template_name = 'shop/card_transfer_pending.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = get_object_or_404(
            Order,
            id=self.kwargs['order_id'],
            user=self.request.user,
        )
        ctx['order'] = order
        ctx['submission'] = CardTransferSubmission.objects.filter(order=order).first()
        ctx['pay_settings'] = _payment_settings()
        return ctx

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(Order, id=kwargs['order_id'], user=request.user)
        if order.status == 'paid':
            return redirect('payment:success', order_id=order.id)
        submission = CardTransferSubmission.objects.filter(order=order).first()
        if submission and submission.status == 'rejected':
            messages.warning(request, 'درخواست پرداخت شما رد شد. لطفاً با پشتیبانی تماس بگیرید.')
            return redirect('dashboard')
        if order.status not in ('pending_verification', 'pending'):
            return redirect('dashboard')
        return super().get(request, *args, **kwargs)


class PaymentCallbackView(View):
    """بازگشت از درگاه پرداخت زیبال"""

    def get(self, request):
        callback_data = {
            'trackId': request.GET.get('trackId'),
            'success': request.GET.get('success'),
            'status': request.GET.get('status'),
            'orderId': request.GET.get('orderId'),
        }
        _log_callback(request, callback_data)

        track_id = callback_data['trackId']
        success_flag = callback_data['success']
        gateway_status = callback_data['status']

        if not track_id:
            request.session['payment_error'] = 'کد پیگیری تراکنش دریافت نشد.'
            return redirect('payment:failed')

        try:
            transaction = Transaction.objects.select_related('order').get(zibal_track_id=track_id)
        except Transaction.DoesNotExist:
            request.session['payment_error'] = 'تراکنش یافت نشد.'
            return redirect('payment:failed')

        order = transaction.order
        request.session['payment_failed_order_id'] = str(order.id)

        transaction.callback_payload = callback_data
        transaction.save(update_fields=['callback_payload'])

        if order.status == 'paid':
            return redirect('payment:success', order_id=order.id)

        if success_flag != '1' or gateway_status != '2':
            error_message = zibal_service.get_callback_status_message(gateway_status)
            if success_flag == '0':
                error_message = 'پرداخت توسط شما لغو شد.'
            transaction.status = 'cancelled' if success_flag == '0' else 'failed'
            transaction.gateway_message = error_message
            transaction.save(update_fields=['status', 'gateway_message'])
            order.status = 'failed'
            order.save(update_fields=['status'])
            request.session['payment_error'] = error_message
            return redirect('payment:failed')

        expected_amount_rial = zibal_service.toman_to_rial(order.amount)

        try:
            verify_result = zibal_service.verify_payment(
                track_id=track_id,
                expected_amount_rial=expected_amount_rial,
            )
        except zibal_service.ZibalConfigurationError:
            request.session['payment_error'] = 'خطا در پیکربندی درگاه پرداخت.'
            return redirect('payment:failed')
        except zibal_service.ZibalVerifyError as exc:
            transaction.status = 'failed'
            transaction.gateway_result_code = exc.result_code
            transaction.gateway_message = exc.message
            transaction.save(update_fields=['status', 'gateway_result_code', 'gateway_message'])
            order.status = 'failed'
            order.save(update_fields=['status'])
            request.session['payment_error'] = exc.message
            return redirect('payment:failed')
        except Exception:
            logger.exception('Zibal verify failed for trackId %s', track_id)
            request.session['payment_error'] = 'خطا در تایید پرداخت. در صورت کسر وجه با پشتیبانی تماس بگیرید.'
            return redirect('payment:failed')

        _finalize_successful_payment(order, transaction, verify_result)
        request.session.pop('payment_error', None)
        request.session.pop('payment_failed_order_id', None)
        return redirect('payment:success', order_id=order.id)


class PaymentSuccessView(LoginRequiredMixin, View):
    """صفحه موفقیت پرداخت"""

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status != 'paid':
            return redirect('dashboard')

        license_obj = License.objects.filter(order=order).first()
        transaction = Transaction.objects.filter(order=order).first()

        context = {
            'order': order,
            'license': license_obj,
            'transaction': transaction,
            'can_download': order_can_download(order),
            'download_filename': get_order_download_filename(order) if order_can_download(order) else '',
        }
        return render(request, 'shop/payment_success.html', context)


class OrderDownloadView(LoginRequiredMixin, View):
    """دانلود فایل نصب ربات — فقط برای سفارش پرداخت‌شده."""

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user=request.user)
        if order.status != 'paid':
            messages.error(request, 'فقط پس از تایید پرداخت می‌توانید فایل را دانلود کنید.')
            return redirect('dashboard')
        if not order_can_download(order):
            messages.error(request, 'فایل نصب برای این محصول تنظیم نشده است.')
            return redirect('payment:success', order_id=order.id)
        log_download(request, order)
        return build_download_response(order)


class PaymentFailedView(TemplateView):
    """صفحه خطای پرداخت"""
    template_name = 'shop/payment_failed.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['error_message'] = self.request.session.pop('payment_error', '')
        failed_order_id = self.request.session.get('payment_failed_order_id')
        ctx['retry_order'] = None
        if failed_order_id:
            try:
                order = Order.objects.select_related('product').get(
                    id=failed_order_id,
                    user=self.request.user,
                )
                if order.status in ('pending', 'failed'):
                    ctx['retry_order'] = order
            except Order.DoesNotExist:
                pass
        return ctx
