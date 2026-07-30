"""API بستن بنر/اطلاعیه."""
from __future__ import annotations

from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator

from shop.services.notice_dismiss import dismiss_notice

ALLOWED_KINDS = frozenset({'announcement', 'banner', 'referral'})


@method_decorator(ensure_csrf_cookie, name='dispatch')
class DismissNoticeView(View):
    """
    POST JSON: { "kind": "announcement"|"banner"|"referral", "id": optional }
    مهمان: نشست. کاربر لاگین: نشست + دیتابیس (دیگر نشان داده نمی‌شود).
    """

    def post(self, request):
        kind = (request.POST.get('kind') or '').strip().lower()
        notice_id = (request.POST.get('id') or '').strip()

        if request.content_type and 'application/json' in request.content_type:
            try:
                import json
                body = json.loads(request.body.decode('utf-8') or '{}')
            except (ValueError, UnicodeDecodeError):
                body = {}
            kind = (body.get('kind') or kind or '').strip().lower()
            raw_id = body.get('id', notice_id)
            notice_id = '' if raw_id is None else str(raw_id).strip()

        if kind not in ALLOWED_KINDS:
            return JsonResponse({'ok': False, 'error': 'kind نامعتبر است.'}, status=400)

        if kind in ('announcement', 'banner') and not notice_id:
            return JsonResponse({'ok': False, 'error': 'شناسه الزامی است.'}, status=400)

        if kind == 'referral':
            notice_id = None

        key = dismiss_notice(request, kind, notice_id)
        return JsonResponse({'ok': True, 'key': key})
