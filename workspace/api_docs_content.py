"""مرجع API و مستندات میزکار — منبع واحد برای قالب docs."""
from __future__ import annotations

import json

from django.conf import settings


def _base_url() -> str:
    return (getattr(settings, 'SITE_URL', '') or 'https://divarfiling.ir').rstrip('/')


def workspace_api_docs(*, has_crm_api_key: bool = False, show_bot_api_key_hint: bool = False) -> dict:
    base = _base_url()
    bot_key_configured = bool(getattr(settings, 'LICENSE_BOT_API_KEY', '') or settings.DEBUG)

    data = {
        'meta': {
            'version': '1.0',
            'base_url': base,
            'api_prefix': f'{base}/api',
            'workspace_prefix': f'{base}/workspace',
        },
        'hero': {
            'eyebrow': 'Developer · API',
            'title': 'مستندات و مرجع API',
            'lead': (
                'راهنمای یکپارچه‌سازی ربات استخراج، CRM و میزکار. '
                'همه endpointها، احراز هویت، نمونه درخواست و پاسخ در یکجا.'
            ),
        },
        'auth_overview': [
            {
                'id': 'bot-api-key',
                'title': 'X-Bot-Api-Key',
                'scope': 'API لایسنس ربات',
                'desc': 'در production برای فعال‌سازی/اعتبارسنجی لایسنس دسکتاپ الزامی است.',
                'header': 'X-Bot-Api-Key',
                'configured': bot_key_configured,
            },
            {
                'id': 'crm-api-key',
                'title': 'X-CRM-API-Key',
                'scope': 'ورود سرنخ CRM',
                'desc': 'کلید اختصاصی آژانس — از صفحه تیم CRM قابل مشاهده و بازتولید است.',
                'header': 'X-CRM-API-Key',
                'has_user_key': has_crm_api_key,
            },
            {
                'id': 'session',
                'title': 'Session Cookie',
                'scope': 'APIهای داخلی میزکار',
                'desc': 'endpointهای JSON داخل میزکار با ورود کاربر (session) محافظت می‌شوند.',
                'header': 'Cookie: sessionid=…',
            },
        ],
        'groups': [
            {
                'id': 'license',
                'title': 'API لایسنس ربات',
                'icon': 'fa-key',
                'accent': 'violet',
                'intro': (
                    'ربات استخراج دسکتاپ از این endpointها برای فعال‌سازی، '
                    'اعتبارسنجی دوره‌ای و غیرفعال‌سازی استفاده می‌کند.'
                ),
                'base_path': f'{base}/api/licenses',
                'auth': {
                    'type': 'header',
                    'name': 'X-Bot-Api-Key',
                    'required_in_production': not settings.DEBUG,
                    'note': 'در حالت DEBUG یا LICENSE_ALLOW_LOCAL_DEV=1 بدون کلید نیز مجاز است.',
                },
                'endpoints': [
                    _license_activate(),
                    _license_validate(),
                    _license_deactivate(),
                ],
            },
            {
                'id': 'crm',
                'title': 'API سرنخ CRM',
                'icon': 'fa-user-plus',
                'accent': 'emerald',
                'intro': 'ثبت خودکار سرنخ (lead) در CRM آژانس از فرم سایت، لندینگ یا اتوماسیون خارجی.',
                'base_path': f'{base}/workspace/crm/api',
                'auth': {
                    'type': 'header',
                    'name': 'X-CRM-API-Key',
                    'required_in_production': True,
                    'note': 'کلید هر آژانس منحصربه‌فرد است.',
                },
                'endpoints': [
                    _crm_leads_inbound(base),
                ],
            },
            {
                'id': 'workspace',
                'title': 'APIهای داخلی میزکار',
                'icon': 'fa-plug',
                'accent': 'sky',
                'intro': 'endpointهای AJAX میزکار — نیاز به ورود کاربر دارند (نه برای integrator خارجی).',
                'base_path': f'{base}/workspace',
                'auth': {
                    'type': 'session',
                    'name': 'Session',
                    'required_in_production': True,
                    'note': 'CSRF token برای POSTهای فرم HTML؛ برخی endpointها JsonResponse برمی‌گردانند.',
                },
                'endpoints': [
                    _ws_onboarding(),
                    _ws_crm_search(base),
                    _ws_crm_quick_lead(base),
                    _ws_listing_benchmark(base),
                ],
            },
        ],
        'errors': {
            'title': 'کدهای خطا',
            'rows': [
                {'code': '200', 'meaning': 'موفق'},
                {'code': '400', 'meaning': 'بدنه یا پارامتر نامعتبر'},
                {'code': '401', 'meaning': 'احراز هویت ناموفق (کلید API یا session)'},
                {'code': '404', 'meaning': 'منبع یافت نشد (لایسنس، فعال‌سازی، …)'},
                {'code': '429', 'meaning': 'تعداد درخواست بیش از حد (rate limit)'},
                {'code': '500', 'meaning': 'خطای سرور'},
            ],
        },
        'guides': [
            {
                'id': 'quickstart-bot',
                'title': 'شروع سریع — ربات',
                'steps': [
                    'کلید لایسنس را از داشبورد کاربر دریافت کنید.',
                    'شناسه سخت‌افزاری را در اپ استخراج کپی کنید.',
                    'POST /api/licenses/activate/ را با license_key و hardware_fingerprint فراخوانی کنید.',
                    'هر ۲۴–۷۲ ساعت validate را برای grace آفلاین اجرا کنید.',
                ],
            },
            {
                'id': 'quickstart-crm',
                'title': 'شروع سریع — CRM',
                'steps': [
                    'از میزکار → تیم CRM کلید API آژانس را بردارید.',
                    'در سرور خود POST /workspace/crm/api/leads/ را با X-CRM-API-Key بزنید.',
                    'فیلدهای name و phone الزامی‌اند؛ source برای گزارش‌گیری توصیه می‌شود.',
                ],
            },
        ],
    }
    _enrich_docs(data)
    return data


def _enrich_docs(data: dict) -> None:
    base = data['meta']['base_url']
    for group in data['groups']:
        auth_header = group['auth']['name']
        for ep in group['endpoints']:
            _enrich_endpoint(ep, base, auth_header)


def _enrich_endpoint(ep: dict, base: str, auth_header: str) -> None:
    path = ep['path']
    url = ep.get('full_url') or f"{base.rstrip('/')}{path}"
    ep['full_url'] = url

    if ep.get('request_example') is not None:
        ep['request_example_json'] = json.dumps(
            ep['request_example'], ensure_ascii=False, indent=2
        )
    if ep.get('response_success') is not None:
        ep['response_success_json'] = json.dumps(
            ep['response_success'], ensure_ascii=False, indent=2
        )
    for err in ep.get('response_errors') or []:
        if err.get('body'):
            err['body_json'] = json.dumps(err['body'], ensure_ascii=False, indent=2)

    extra = ep.get('curl_extra_headers') or []
    headers = [f'-H "Content-Type: application/json"']
    if auth_header and auth_header not in ('Session',):
        key_placeholder = 'YOUR_API_KEY'
        if auth_header == 'X-CRM-API-Key':
            key_placeholder = 'YOUR_AGENCY_API_KEY'
        elif auth_header == 'X-Bot-Api-Key':
            key_placeholder = 'YOUR_BOT_API_KEY'
        headers.append(f'-H "{auth_header}: {key_placeholder}"')
    for h in extra:
        headers.append(f'-H "{h}"')

    method = ep['method']
    if method == 'GET':
        ep['curl_example'] = f'curl -X GET "{url}" \\\n  ' + ' \\\n  '.join(headers)
    else:
        body = ep.get('request_example_json', '{}')
        ep['curl_example'] = (
            f'curl -X {method} "{url}" \\\n  '
            + ' \\\n  '.join(headers)
            + f" \\\n  -d '{body}'"
        )


def _field(name, ftype, required=False, desc=''):
    return {'name': name, 'type': ftype, 'required': required, 'desc': desc}


def _license_activate():
    return {
        'id': 'license-activate',
        'method': 'POST',
        'path': '/api/licenses/activate/',
        'title': 'فعال‌سازی لایسنس',
        'summary': 'ثبت یا فعال‌سازی لایسنس روی یک دستگاه جدید.',
        'request_fields': [
            _field('license_key', 'string', True, 'کلید لایسنس (فرمت استاندارد پلتفرم)'),
            _field('hardware_fingerprint', 'string', True, 'SHA-256 شناسه سخت‌افزاری دستگاه'),
        ],
        'request_example': {
            'license_key': 'DFL-XXXX-XXXX-XXXX',
            'hardware_fingerprint': 'a1b2c3d4e5f6…64chars',
        },
        'response_success': {
            'success': True,
            'message': 'لایسنس با موفقیت فعال شد.',
            'license_key': 'DFL-XXXX-XXXX-XXXX',
            'activated_at': '2026-06-20T10:00:00+00:00',
            'offline_grace_until': '2026-06-23T10:00:00+00:00',
            'offline_grace_hours': 72,
            'server_time': '2026-06-20T10:00:00+00:00',
            'plan_id': 1,
            'plan_name': 'ربات ماهانه',
            'max_activations': 2,
            'expires_at': '2026-07-20T00:00:00+00:00',
        },
        'response_errors': [
            {'status': 400, 'body': {'error': 'لایسنس منقضی شده یا غیرفعال است.'}},
            {'status': 404, 'body': {'error': 'لایسنس معتبر نیست.'}},
            {'status': 429, 'body': {'error': 'تعداد درخواست بیش از حد مجاز است.'}},
        ],
    }


def _license_validate():
    return {
        'id': 'license-validate',
        'method': 'POST',
        'path': '/api/licenses/validate/',
        'title': 'اعتبارسنجی لایسنس',
        'summary': 'بررسی وضعیت لایسنس و فعال بودن روی دستگاه فعلی.',
        'request_fields': [
            _field('license_key', 'string', True, 'کلید لایسنس'),
            _field('hardware_fingerprint', 'string', True, 'شناسه سخت‌افزاری'),
        ],
        'request_example': {
            'license_key': 'DFL-XXXX-XXXX-XXXX',
            'hardware_fingerprint': 'a1b2c3d4e5f6…',
        },
        'response_success': {
            'valid': True,
            'license_key': 'DFL-XXXX-XXXX-XXXX',
            'status': 'active',
            'is_activated': True,
            'offline_grace_until': '2026-06-23T10:00:00+00:00',
            'plan_name': 'ربات ماهانه',
            'expires_at': '2026-07-20T00:00:00+00:00',
        },
        'response_errors': [
            {'status': 404, 'body': {'valid': False, 'error': 'لایسنس یافت نشد.'}},
        ],
    }


def _license_deactivate():
    return {
        'id': 'license-deactivate',
        'method': 'POST',
        'path': '/api/licenses/deactivate/',
        'title': 'غیرفعال‌سازی لایسنس',
        'summary': 'آزاد کردن اسلات دستگاه از لایسنس.',
        'request_fields': [
            _field('license_key', 'string', True, 'کلید لایسنس'),
            _field('hardware_fingerprint', 'string', True, 'شناسه سخت‌افزاری'),
        ],
        'request_example': {
            'license_key': 'DFL-XXXX-XXXX-XXXX',
            'hardware_fingerprint': 'a1b2c3d4e5f6…',
        },
        'response_success': {
            'success': True,
            'message': 'لایسنس با موفقیت غیرفعال شد.',
        },
        'response_errors': [
            {'status': 404, 'body': {'error': 'لایسنس یا فعال‌سازی یافت نشد.'}},
        ],
    }


def _crm_leads_inbound(base: str):
    return {
        'id': 'crm-leads',
        'method': 'POST',
        'path': '/workspace/crm/api/leads/',
        'title': 'ثبت سرنخ',
        'summary': 'ایجاد مخاطب/سرنخ جدید در CRM آژانس.',
        'request_fields': [
            _field('name', 'string', True, 'نام سرنخ'),
            _field('phone', 'string', True, 'شماره موبایل (ایران)'),
            _field('source', 'string', False, 'منبع — پیش‌فرض: API'),
            _field('notes', 'string', False, 'یادداشت اختیاری'),
        ],
        'request_example': {
            'name': 'علی محمدی',
            'phone': '09121234567',
            'source': 'website-form',
            'notes': 'علاقه‌مند به خرید آپارتمان',
        },
        'response_success': {
            'ok': True,
            'id': 42,
            'name': 'علی محمدی',
        },
        'response_errors': [
            {'status': 400, 'body': {'ok': False, 'error': 'Bad JSON'}},
            {'status': 401, 'body': {'ok': False, 'error': 'Unauthorized'}},
            {'status': 429, 'body': {'ok': False, 'error': 'Too many requests'}},
        ],
        'curl_extra_headers': ['X-CRM-API-Key: YOUR_AGENCY_API_KEY'],
        'full_url': f'{base}/workspace/crm/api/leads/',
    }


def _ws_onboarding():
    return {
        'id': 'ws-onboarding',
        'method': 'POST',
        'path': '/workspace/api/onboarding/complete/',
        'title': 'تکمیل onboarding',
        'summary': 'علامت‌گذاری تور اولیه میزکار به‌عنوان انجام‌شده.',
        'internal': True,
        'request_fields': [],
        'request_example': {},
        'response_success': {'ok': True},
        'response_errors': [],
    }


def _ws_crm_search(base: str):
    return {
        'id': 'ws-crm-search',
        'method': 'GET',
        'path': '/workspace/crm/search/',
        'title': 'جستجوی سراسری CRM',
        'summary': 'جستجو در مخاطبین، معاملات و فایل‌ها.',
        'internal': True,
        'query_params': [
            _field('q', 'string', True, 'عبارت جستجو'),
        ],
        'request_example': None,
        'response_success': {'results': []},
        'response_errors': [],
        'full_url': f'{base}/workspace/crm/search/?q=0912',
    }


def _ws_crm_quick_lead(base: str):
    return {
        'id': 'ws-crm-quick-lead',
        'method': 'POST',
        'path': '/workspace/crm/contacts/quick/',
        'title': 'ثبت سریع سرنخ',
        'summary': 'ایجاد مخاطب از drawer میزکار (session + CSRF).',
        'internal': True,
        'request_fields': [
            _field('name', 'string', True, 'نام'),
            _field('phone', 'string', False, 'تلفن'),
        ],
        'request_example': {'name': 'رضا', 'phone': '09120001122'},
        'response_success': {'ok': True, 'id': 10},
        'response_errors': [],
        'full_url': f'{base}/workspace/crm/contacts/quick/',
    }


def _ws_listing_benchmark(base: str):
    return {
        'id': 'ws-benchmark',
        'method': 'GET',
        'path': '/workspace/datasets/{dataset_id}/listings/{listing_id}/benchmark/',
        'title': 'بنچمارک قیمت آگهی',
        'summary': 'مقایسه قیمت یک آگهی با میانگین محله (نیاز به لایسنس ربات).',
        'internal': True,
        'request_fields': [],
        'request_example': None,
        'response_success': {'ok': True, 'benchmark': {}},
        'response_errors': [],
    }
