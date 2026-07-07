"""
Unified referral attribution — cookie, session, user.referred_by, order.affiliate
"""
from __future__ import annotations

from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from affiliates.models import Affiliate

SESSION_KEY = 'affiliate_ref_code'


def resolve_affiliate_by_code(code: str | None) -> Affiliate | None:
    if not code:
        return None
    code = str(code).strip().upper()
    if not code:
        return None
    try:
        return Affiliate.objects.select_related('user').get(code__iexact=code, is_active=True)
    except Affiliate.DoesNotExist:
        return None


def is_valid_attribution(buyer, affiliate: Affiliate | None) -> bool:
    """Reject self-referral and inactive affiliates."""
    if not affiliate or not affiliate.is_active:
        return False
    if not buyer or not getattr(buyer, 'is_authenticated', False):
        return True
    if buyer.is_authenticated and affiliate.user_id == buyer.pk:
        return False
    return True


def capture_referral_from_request(request) -> Affiliate | None:
    """Read referral from query string, cookie, or session (priority: query > cookie > session)."""
    code = request.GET.get('ref') or request.COOKIES.get(settings.AFFILIATE_COOKIE_NAME)
    if not code:
        code = request.session.get(SESSION_KEY)
    return resolve_affiliate_by_code(code)


def store_referral_on_response(request, response, affiliate: Affiliate) -> None:
    """Persist referral code in cookie + session."""
    if not affiliate:
        return
    code = affiliate.code
    request.session[SESSION_KEY] = code
    request.session.modified = True
    max_age = settings.AFFILIATE_COOKIE_DAYS * 24 * 60 * 60
    response.set_cookie(
        settings.AFFILIATE_COOKIE_NAME,
        code,
        max_age=max_age,
        httponly=True,
        samesite='Lax',
        secure=getattr(settings, 'SESSION_COOKIE_SECURE', False),
    )


def build_referral_url(request, affiliate: Affiliate, path: str = '/') -> str:
    base = request.build_absolute_uri(path)
    sep = '&' if '?' in base else '?'
    return f'{base}{sep}ref={affiliate.code}'


def assign_referred_user(user, affiliate: Affiliate | None) -> bool:
    """
    Bind referred_by once (first-touch). Returns True if assigned or already same affiliate.
    """
    if not affiliate or not is_valid_attribution(user, affiliate):
        return False
    if user.referred_by_id:
        return user.referred_by_id == affiliate.pk
    user.referred_by = affiliate
    user.save(update_fields=['referred_by'])
    return True


def resolve_order_affiliate(user, request) -> Affiliate | None:
    """
    Determine affiliate credit for an order.
    Priority: existing referred_by > session/cookie (late attribution if referred_by empty).
    """
    if user.referred_by_id and is_valid_attribution(user, user.referred_by):
        return user.referred_by

    captured = capture_referral_from_request(request)
    if captured and is_valid_attribution(user, captured):
        if not user.referred_by_id:
            assign_referred_user(user, captured)
        if user.referred_by_id == captured.pk:
            return captured
    return None


def get_referral_destination(request, affiliate: Affiliate) -> str | None:
    """
    Smart redirect target when landing with ?ref= on homepage.
    Returns None if no redirect needed.
    """
    if not affiliate or not is_valid_attribution(request.user, affiliate):
        return None

    path = (request.path or '/').rstrip('/') or '/'
    if path != '/':
        return None
    if request.GET.get('ref', '').strip().upper() != affiliate.code.upper():
        return None

    user = request.user
    if user.is_authenticated:
        from shop.models import Order
        has_paid = Order.objects.filter(user=user, status='paid').exists()
        if has_paid:
            return None
        from shop.bot_catalog import get_bot_product_buy_url
        buy_url = get_bot_product_buy_url()
        return f'{buy_url}?{urlencode({"ref": affiliate.code})}'

    register_url = reverse('register')
    return f'{register_url}?{urlencode({"ref": affiliate.code})}'


def get_referral_banner_context(request) -> dict | None:
    """Context for referral welcome banner on public pages."""
    affiliate = capture_referral_from_request(request)
    if not affiliate:
        return None
    if request.user.is_authenticated and not is_valid_attribution(request.user, affiliate):
        return None

    discount = affiliate.discount_percentage or Decimal(str(settings.AFFILIATE_DEFAULT_DISCOUNT))
    discount_int = int(discount)

    referrer_name = (
        affiliate.user.get_full_name()
        or affiliate.user.username
        or 'همکار فایلینگ دیوار'
    )

    user = request.user
    if user.is_authenticated:
        from shop.models import Order
        has_paid = Order.objects.filter(user=user, status='paid').exists()
        if has_paid:
            cta_url = reverse('product_list')
            cta_text = 'مشاهده محصولات'
        else:
            from shop.bot_catalog import get_bot_product_buy_url
            cta_url = f'{get_bot_product_buy_url()}?{urlencode({"ref": affiliate.code})}'
            cta_text = 'خرید با تخفیف معرف'
    else:
        cta_url = f'{reverse("register")}?{urlencode({"ref": affiliate.code})}'
        cta_text = 'ثبت‌نام رایگان'

    return {
        'affiliate': affiliate,
        'referrer_name': referrer_name,
        'referrer_code': affiliate.code,
        'discount_percent': discount_int,
        'discount_label': f'{discount_int}٪ تخفیف ویژه',
        'cta_url': cta_url,
        'cta_text': cta_text,
        'is_authenticated': user.is_authenticated,
    }
