"""وب‌هوک CRM — C8."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

import requests
from django.utils import timezone

from workspace.models import CRMAgency, CRMAgencyWebhook, Customer
from workspace.services.crm import log_activity

logger = logging.getLogger(__name__)


def dispatch_webhook(agency: CRMAgency, event: str, payload: dict) -> None:
    hooks = CRMAgencyWebhook.objects.filter(agency=agency, is_active=True)
    for hook in hooks:
        events = hook.events or []
        if events and event not in events:
            continue
        body = {'event': event, 'timestamp': timezone.now().isoformat(), 'data': payload}
        raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type': 'application/json'}
        if hook.secret:
            sig = hmac.new(hook.secret.encode(), raw, hashlib.sha256).hexdigest()
            headers['X-CRM-Signature'] = sig
        try:
            requests.post(hook.url, data=raw, headers=headers, timeout=8)
        except requests.RequestException as exc:
            logger.warning('webhook failed %s: %s', hook.url, exc)


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
    log_activity(customer, 'یادداشت', title='ورود API', content='سرنخ از وب‌هوک/API')
    dispatch_webhook(agency, 'customer.created', {
        'id': customer.pk, 'name': customer.name, 'phone': customer.phone,
    })
    return customer


def verify_api_key(agency: CRMAgency, key: str) -> bool:
    return bool(key and agency.api_key and hmac.compare_digest(agency.api_key, key))
