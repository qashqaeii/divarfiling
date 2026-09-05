"""ورود/ثبت‌نام/OTP و فروشگاه برای API موبایل."""
from __future__ import annotations

from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from mobile_api.responses import api_error, api_ok
from mobile_api.serializers import user_to_dict
from mobile_api.services.auth_otp_service import (
    MobileAuthError,
    complete_password_reset,
    complete_register,
    complete_verify_phone,
    request_public_otp,
    request_verify_phone_otp,
    resend_public_otp,
    verify_login_otp,
    verify_step_otp,
)
from mobile_api.services.shop_checkout_service import (
    MobileShopError,
    create_checkout,
    list_mobile_plans,
    order_status_payload,
    preview_plan_discount,
    preview_plan_pricing,
    verify_mobile_order,
)
from mobile_api.throttles import MobileLoginThrottle, MobileUserThrottle
from mobile_api.views import _parse_body, _tokens_for_user


def _auth_error(exc: MobileAuthError):
    extra = {}
    if exc.retry_after:
        extra['retry_after'] = exc.retry_after
    body = api_error(exc.message, code=exc.code, status=exc.status)
    if extra:
        body.data.update(extra)
    return body


def _shop_error(exc: MobileShopError):
    return api_error(exc.message, code=exc.code, status=exc.status)


class OtpRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        try:
            payload = request_public_otp(
                data.get('phone') or '',
                data.get('purpose') or '',
                request=request,
            )
            return api_ok(payload)
        except MobileAuthError as exc:
            return _auth_error(exc)


class OtpResendView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        try:
            payload = resend_public_otp(
                data.get('phone') or '',
                data.get('purpose') or '',
                request=request,
            )
            return api_ok(payload)
        except MobileAuthError as exc:
            return _auth_error(exc)


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        phone = data.get('phone') or ''
        purpose = (data.get('purpose') or '').strip().lower()
        code = data.get('code') or ''
        try:
            if purpose == 'login':
                user = verify_login_otp(phone, code)
                return api_ok({**_tokens_for_user(user), 'user': user_to_dict(user)})
            payload = verify_step_otp(phone, purpose, code)
            return api_ok(payload)
        except MobileAuthError as exc:
            return _auth_error(exc)


class RegisterCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        try:
            user = complete_register(
                data.get('phone') or '',
                data.get('challenge_token') or '',
                data.get('password') or data.get('password1') or '',
                data.get('password_confirm') or data.get('password2') or '',
                request=request,
            )
            return api_ok({**_tokens_for_user(user), 'user': user_to_dict(user)}, status=201)
        except MobileAuthError as exc:
            return _auth_error(exc)


class PasswordResetCompleteView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        try:
            complete_password_reset(
                data.get('phone') or '',
                data.get('challenge_token') or '',
                data.get('password') or data.get('password1') or '',
                data.get('password_confirm') or data.get('password2') or '',
            )
            return api_ok({'ok': True, 'message': 'رمز عبور با موفقیت تغییر کرد. اکنون وارد شوید.'})
        except MobileAuthError as exc:
            return _auth_error(exc)


class VerifyPhoneRequestView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        try:
            return api_ok(request_verify_phone_otp(request.user, request=request))
        except MobileAuthError as exc:
            return _auth_error(exc)


class VerifyPhoneCompleteView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileLoginThrottle]

    def post(self, request):
        data = _parse_body(request)
        try:
            user = complete_verify_phone(request.user, data.get('code') or '')
            return api_ok({'user': user_to_dict(user)})
        except MobileAuthError as exc:
            return _auth_error(exc)


class ShopPlansView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileUserThrottle]

    def get(self, request):
        try:
            return api_ok(list_mobile_plans(request.user))
        except MobileShopError as exc:
            return _shop_error(exc)


class ShopCheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileUserThrottle]

    def post(self, request):
        data = _parse_body(request)
        plan_id = data.get('plan_id')
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError):
            return api_error('پلن را انتخاب کنید.', code='VALIDATION_ERROR')
        renew_id = data.get('renew_license_id') or data.get('license_id')
        discount_code = data.get('discount_code') or data.get('coupon') or ''
        quantity = data.get('quantity', 1)
        try:
            payload = create_checkout(
                request.user,
                plan_id=plan_id,
                renew_license_id=int(renew_id) if renew_id else None,
                discount_code=str(discount_code).strip() or None,
                quantity=quantity,
                request=request,
            )
            return api_ok(payload)
        except MobileShopError as exc:
            return _shop_error(exc)


class ShopDiscountPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileUserThrottle]

    def post(self, request):
        data = _parse_body(request)
        plan_id = data.get('plan_id')
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError):
            return api_error('پلن را انتخاب کنید.', code='VALIDATION_ERROR')
        code = (data.get('discount_code') or data.get('coupon') or '').strip()
        quantity = data.get('quantity', 1)
        try:
            if not code:
                return api_ok(preview_plan_pricing(
                    request.user,
                    plan_id=plan_id,
                    quantity=quantity,
                    request=request,
                ))
            return api_ok(preview_plan_discount(
                request.user,
                plan_id=plan_id,
                discount_code=code,
                quantity=quantity,
                request=request,
            ))
        except MobileShopError as exc:
            return _shop_error(exc)


class ShopOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MobileUserThrottle]

    def get(self, request, order_id):
        try:
            return api_ok(order_status_payload(request.user, order_id))
        except MobileShopError as exc:
            return _shop_error(exc)

    def post(self, request, order_id):
        try:
            return api_ok(verify_mobile_order(request.user, order_id))
        except MobileShopError as exc:
            return _shop_error(exc)
