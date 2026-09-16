"""ویوی پل session اپ → میزکار."""
from __future__ import annotations

from django.contrib.auth import login
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.views import View

from mobile_api.services.workspace_bridge import consume_bridge_token


class WorkspaceAppBridgeView(View):
    """مصرف توکن یک‌بارمصرف و ورود session برای WebView."""

    def get(self, request, token):
        payload = consume_bridge_token(token)
        if not payload:
            raise Http404('لینک منقضی یا نامعتبر است.')
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.filter(pk=payload.get('user_id')).first()
        if not user or not user.is_active:
            raise Http404('کاربر یافت نشد.')
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        path = payload.get('path') or '/workspace/'
        return redirect(path)
