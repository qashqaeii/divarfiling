"""Affiliate context for templates."""
from affiliates.services.referral import get_referral_banner_context


def affiliate_context(request):
    banner = get_referral_banner_context(request)
    return {
        'referral_banner': banner,
        'active_referral': banner['affiliate'] if banner else None,
    }
