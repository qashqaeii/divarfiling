"""Affiliate context for templates."""
from affiliates.services.referral import get_referral_banner_context
from shop.services.notice_dismiss import is_dismissed


def affiliate_context(request):
    if is_dismissed(request, 'referral'):
        return {
            'referral_banner': None,
            'active_referral': None,
        }
    banner = get_referral_banner_context(request)
    return {
        'referral_banner': banner,
        'active_referral': banner['affiliate'] if banner else None,
    }
