"""
Middleware — referral capture, persistence, smart redirect
"""
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin

from affiliates.services.referral import (
    capture_referral_from_request,
    get_referral_destination,
    resolve_affiliate_by_code,
    store_referral_on_response,
)


class AffiliateTrackingMiddleware(MiddlewareMixin):
    """Track ?ref= links via cookie + session; redirect guests intelligently."""

    def process_request(self, request):
        ref_code = request.GET.get('ref')
        if not ref_code:
            return None

        affiliate = resolve_affiliate_by_code(ref_code)
        if not affiliate:
            return None

        request._affiliate_ref = affiliate  # noqa: SLF001

        destination = get_referral_destination(request, affiliate)
        if destination:
            return HttpResponseRedirect(destination)
        return None

    def process_response(self, request, response):
        affiliate = getattr(request, '_affiliate_ref', None)
        if not affiliate and request.GET.get('ref'):
            affiliate = resolve_affiliate_by_code(request.GET.get('ref'))
        if affiliate:
            store_referral_on_response(request, response, affiliate)
        return response

    @staticmethod
    def get_affiliate_from_request(request):
        """Backward-compatible helper."""
        return capture_referral_from_request(request)
