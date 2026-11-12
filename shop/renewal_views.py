"""صفحات و API تمدید چندلایسنسی از روی سفارش مبدأ."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from licenses.services.renewal_orders import (
    RenewalOrderError,
    create_renewal_order,
    list_renewable_licenses_for_source_order,
    quote_renewal_order,
)
from shop.models import Order, LicensePlan


class OrderRenewView(LoginRequiredMixin, View):
    """انتخاب لایسنس‌ها برای تمدید — سفارش مبدأ پرداخت‌شده."""

    template_name = 'shop/order_renew.html'

    def _source_order(self, request, source_order_id):
        return get_object_or_404(
            Order.objects.select_related('product', 'plan'),
            pk=source_order_id,
            user=request.user,
            status='paid',
        )

    def get(self, request, source_order_id):
        source_order = self._source_order(request, source_order_id)
        context = list_renewable_licenses_for_source_order(request.user, source_order.pk)
        plans = list(
            source_order.product.plans.filter(is_active=True).order_by('order', 'price')
        )
        context.update({
            'source_order': source_order,
            'plans': plans,
            'selected_plan_id': int(request.GET.get('plan') or source_order.plan_id),
        })
        return render(request, self.template_name, context)


class OrderRenewQuoteView(LoginRequiredMixin, View):
    """پیش‌نمایش قیمت تمدید — JSON."""

    def post(self, request, source_order_id):
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر است.'}, status=400)

        license_ids = payload.get('license_ids') or []
        plan_id = payload.get('plan_id')
        discount_code = (payload.get('discount_code') or '').strip()

        try:
            quote = quote_renewal_order(
                request.user,
                source_order_id,
                license_ids=license_ids,
                plan_id=int(plan_id) if plan_id else None,
                discount_code_str=discount_code,
                request=request,
            )
        except RenewalOrderError as exc:
            return JsonResponse({'ok': False, 'error': exc.message, 'code': exc.code}, status=400)

        return JsonResponse({'ok': True, 'quote': quote})


class OrderRenewCheckoutView(LoginRequiredMixin, View):
    """ایجاد سفارش تمدید و هدایت به پرداخت."""

    def post(self, request, source_order_id):
        license_ids = request.POST.getlist('license_ids')
        if not license_ids:
            raw = (request.POST.get('license_ids') or '').strip()
            if raw:
                license_ids = [x.strip() for x in raw.split(',') if x.strip()]
        try:
            license_ids = [int(x) for x in license_ids]
        except (TypeError, ValueError):
            messages.error(request, 'انتخاب لایسنس نامعتبر است.')
            return redirect('order_renew', source_order_id=source_order_id)

        plan_id = request.POST.get('plan_id')
        discount_code = (request.POST.get('discount_code') or '').strip()

        try:
            order = create_renewal_order(
                request.user,
                source_order_id,
                license_ids=license_ids,
                plan_id=int(plan_id) if plan_id else None,
                discount_code_str=discount_code,
                request=request,
            )
        except RenewalOrderError as exc:
            messages.error(request, exc.message)
            return redirect('order_renew', source_order_id=source_order_id)

        return redirect('payment:checkout', order_id=order.id)
