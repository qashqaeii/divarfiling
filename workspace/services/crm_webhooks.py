"""وب‌هوک CRM — C8."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyWebhook, CRMAgencyWebhookDelivery, Customer
from workspace.services.crm import log_activity
from workspace.services.crm_agency import apply_lead_routing

logger = logging.getLogger(__name__)


def _post_webhook(hook: CRMAgencyWebhook, event: str, body: dict) -> Tuple[bool, Optional[int], str]:
    raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if hook.secret:
        sig = hmac.new(hook.secret.encode(), raw, hashlib.sha256).hexdigest()
        headers['X-CRM-Signature'] = sig
    try:
        resp = requests.post(hook.url, data=raw, headers=headers, timeout=8)
        ok = 200 <= resp.status_code < 300
        CRMAgencyWebhookDelivery.objects.create(
            webhook=hook,
            event=event,
            status_code=resp.status_code,
            success=ok,
            error='' if ok else resp.text[:300],
        )
        return ok, resp.status_code, '' if ok else resp.text[:300]
    except requests.RequestException as exc:
        CRMAgencyWebhookDelivery.objects.create(
            webhook=hook,
            event=event,
            success=False,
            error=str(exc)[:300],
        )
        logger.warning('webhook failed %s: %s', hook.url, exc)
        return False, None, str(exc)[:300]


def dispatch_webhook(agency: CRMAgency, event: str, payload: dict) -> None:
    hooks = CRMAgencyWebhook.objects.filter(agency=agency, is_active=True)
    body = {'event': event, 'timestamp': timezone.now().isoformat(), 'data': payload}
    for hook in hooks:
        events = hook.events or []
        if events and event not in events:
            continue
        _post_webhook(hook, event, body)


def test_webhook(hook: CRMAgencyWebhook) -> Tuple[bool, str]:
    body = {
        'event': 'webhook.test',
        'timestamp': timezone.now().isoformat(),
        'data': {'message': 'تست وب‌هوک فایلینگ دیوار'},
    }
    ok, _code, err = _post_webhook(hook, 'webhook.test', body)
    return ok, err or 'ارسال موفق'


def create_lead_from_api(
    agency: CRMAgency,
    *,
    owner_user,
    name: str,
    phone: str = '',
    source: str = 'API',
    notes: str = '',
) -> Customer:
    name = (name or '').strip()
    if not name:
        raise ValueError('نام الزامی است')
    customer = Customer.objects.create(
        user=owner_user,
        agency=agency,
        name=name,
        phone=(phone or '').strip(),
        source=source or 'سایر',
        customer_type='سرنخ',
        status='جدید',
        notes=notes or '',
    )
    apply_lead_routing(agency, customer)
    log_activity(customer, 'یادداشت', title='ورود API', content='سرنخ از وب‌هوک/API')
    dispatch_webhook(agency, 'customer.created', {
        'id': customer.pk, 'name': customer.name, 'phone': customer.phone,
    })
    return customer


def verify_api_key(agency: CRMAgency, key: str) -> bool:
    return bool(key and agency.api_key and hmac.compare_digest(agency.api_key, key))
