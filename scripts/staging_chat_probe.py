"""Probe public-assistant chat API (CSRF session). Usage: python scripts/staging_chat_probe.py [base_url]"""
from __future__ import annotations

import json
import sys
import time
from urllib.parse import urljoin

import requests

QUESTIONS = [
    ('چطوری فایل شخصی داشته باشم', ['فایل شخصی', 'crm', 'ملک']),
    ('شماره مالک کجا وارد میشه', ['اطلاعات پایه', 'crm', 'مالک']),
    ('چطوری لینک برای مشتری بفرستم', ['اشتراک', 'لینک', 'مشتری']),
    ('چطور مخاطب ثبت کنم', ['مخاطب', 'contacts']),
    ('لینک مشتری باز نمیشه', ['فعال', 'لینک']),
]

OWNER_PHONE_FORBIDDEN = [
    'سوئیچ نمایش شماره مالک',
    'نمایش شماره مالک را فعال',
    'سوئیچ‌های تماس/آدرس را فعال کنید تا شماره مالک',
]


def probe(base: str) -> dict:
    base = base.rstrip('/') + '/'
    s = requests.Session()
    s.headers.update({'User-Agent': 'DivarFiling-Wave1-Release-Gate/1.0'})
    cfg_url = urljoin(base, 'api/public-assistant/config/')
    chat_url = urljoin(base, 'api/public-assistant/chat/')
    r = s.get(cfg_url, timeout=30)
    r.raise_for_status()
    csrf = s.cookies.get('csrftoken')
    if not csrf:
        raise RuntimeError('no csrftoken cookie')
    out = {'base': base, 'config_ok': True, 'turns': []}
    for q, must_hints in QUESTIONS:
        time.sleep(1.2)
        resp = s.post(
            chat_url,
            json={'message': q},
            headers={'X-CSRFToken': csrf, 'Referer': base},
            timeout=90,
        )
        body = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        answer = (body.get('answer') or '')[:4000]
        bad_owner = [p for p in OWNER_PHONE_FORBIDDEN if p in answer]
        hints_ok = sum(1 for h in must_hints if h.lower() in answer.lower() or h in answer)
        out['turns'].append(
            {
                'question': q,
                'status': resp.status_code,
                'ok': body.get('ok'),
                'low_confidence': body.get('low_confidence'),
                'from_fallback': body.get('from_fallback'),
                'hint_hits': hints_ok,
                'hints_required': len(must_hints),
                'bad_owner_claims': bad_owner,
                'answer_preview': answer[:1200],
                'sources': [x.get('url') for x in (body.get('sources') or [])[:5]],
            }
        )
    return out


if __name__ == '__main__':
    base = sys.argv[1] if len(sys.argv) > 1 else 'https://divarfiling.ir'
    out_path = sys.argv[2] if len(sys.argv) > 2 else ''
    result = probe(base)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if out_path:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(text)
    else:
        sys.stdout.buffer.write(text.encode('utf-8'))
