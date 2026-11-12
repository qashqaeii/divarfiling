"""لینک‌های فارسی مارک‌داون برای پاسخ دستیار عمومی."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

from public_assistant.services.security import is_allowed_public_link

if TYPE_CHECKING:
    from public_assistant.services.public_plans import PublicPlanCatalog, PublicPlanInfo

_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
_MD_PLACEHOLDER = '__PA_MD_LINK_{}__'

_PATH_LABELS: dict[str, str] = {
    '/': 'صفحه اصلی فایلینگ دیوار',
    '/workspace/': 'ورود به میزکار',
    '/workspace/support/': 'پشتیبانی',
    '/contact/': 'تماس با پشتیبانی',
    '/license-guide/': 'راهنمای فعال‌سازی لایسنس',
    '/products/': 'محصولات و اشتراک',
    '/products/divar-extraction-bot/buy/': 'خرید اشتراک فایلینگ دیوار',
    '/payment/': 'پرداخت',
    '/academy/': 'آکادمی',
    '/privacy/': 'حریم خصوصی',
    '/affiliate/': 'برنامه معرف',
    '/download/windows/': 'دانلود نرم‌افزار ویندوز',
    '/amoozesh/android/': 'آموزش اندروید',
}

_PLAN_TYPE_LABEL = {
    'daily': 'آزمایشی',
    'monthly': 'ماهانه',
    'quarterly': 'سه‌ماهه',
    'yearly': 'یک‌ساله',
}

_PREFIX_PATH_RE = re.compile(
    r'(?P<prefix>خرید رسمی|صفحه خرید(?: آژانس)?|راهنما|قدم بعدی)\s*:\s*(?P<path>/[^\s\n]+)'
)
_BACKTICK_PATH_RE = re.compile(r'`(/[^`\s]+)`')
_BARE_PATH_LINE_RE = re.compile(
    r'^(?P<path>/(?:products|workspace|contact|license-guide|payment|academy)[^\s]*)\s*$',
    re.MULTILINE,
)
_INLINE_BACKTICK_PATH_RE = re.compile(
    r'(?P<lead>[^[\n]{0,120}?)(?P<tick>`(?P<path>/[^`]+)`)(?P<trail>[\.،؛!\s]*)'
)
_HTML_TAG_RE = re.compile(r'<[^>]+>')


def md_link(label: str, url: str) -> str:
    """[عنوان فارسی](url) — در صورت مسیر نامعتبر فقط عنوان."""
    from public_assistant.services.public_paths import canonical_public_path

    label = (label or '').strip() or 'لینک'
    url = canonical_public_path((url or '').strip())
    if not is_allowed_public_link(url):
        return label
    return f'[{label}]({url})'


def _path_key(path: str) -> str:
    p = (path or '').strip()
    if not p.startswith('/'):
        return p
    base = p.split('?')[0].rstrip('/') + '/'
    if base in _PATH_LABELS:
        return base
    return p.split('?')[0]


def label_for_path(path: str) -> str:
    url = (path or '').strip()
    if not url:
        return 'لینک'
    base = url.split('?')[0]
    if base in _PATH_LABELS:
        label = _PATH_LABELS[base]
    elif base.rstrip('/') + '/' in _PATH_LABELS:
        label = _PATH_LABELS[base.rstrip('/') + '/']
    elif '/products/divar-extraction-bot/buy/' in base:
        label = 'خرید اشتراک فایلینگ دیوار'
    elif base.startswith('/workspace/crm/'):
        label = 'بخش CRM میزکار'
    elif base.startswith('/workspace/'):
        label = 'میزکار'
    else:
        label = 'صفحه مرتبط در سایت'
    qs = parse_qs(urlparse(url).query)
    plan_ids = qs.get('plan')
    if plan_ids and plan_ids[0].isdigit():
        label = f'{label} (پلن {plan_ids[0]})'
    return label


def buy_link_label(plan: PublicPlanInfo | None, url: str = '') -> str:
    if plan:
        dur = _PLAN_TYPE_LABEL.get(plan.plan_type, plan.duration_label or '')
        if plan.segment == 'agency':
            return f'خرید اشتراک {dur} آژانس'.replace('  ', ' ').strip()
        if plan.segment == 'trial':
            return 'خرید پلن آزمایشی'
        if dur:
            return f'خرید اشتراک {dur} شخصی'
        name = (plan.name or '').strip()
        if name:
            return f'خرید {name}'
    return label_for_path(url or '/products/divar-extraction-bot/buy/')


def plan_purchase_markdown(
    plan: PublicPlanInfo | None,
    catalog: PublicPlanCatalog | None = None,
    *,
    inline: bool = True,
) -> str:
    if plan:
        url = plan.buy_url
    elif catalog:
        url = catalog.product_buy_url
    else:
        url = '/products/divar-extraction-bot/buy/'
    link = md_link(buy_link_label(plan, url), url)
    if not inline:
        return link
    return f'برای خرید و فعال‌سازی، {link} را ببینید.'


def workspace_link(inline: bool = True) -> str:
    link = md_link('ورود به میزکار', '/workspace/')
    if inline:
        return f'برای مدیریت فایل‌ها و مشتری‌ها، {link} کنید.'
    return link


def support_link(inline: bool = False) -> str:
    link = md_link('پشتیبانی', '/workspace/support/')
    if inline:
        return f'از {link} کمک بگیرید'
    return link


def contact_link(inline: bool = False) -> str:
    link = md_link('تماس با پشتیبانی', '/contact/')
    if inline:
        return f'با {link} هماهنگ کنید'
    return link


def license_guide_link(inline: bool = False) -> str:
    link = md_link('راهنمای فعال‌سازی لایسنس', '/license-guide/')
    if inline:
        return f'در {link} جزئیات را ببینید'
    return link


def _protect_markdown_links(text: str) -> tuple[str, list[str]]:
    links: list[str] = []

    def _keep(m: re.Match[str]) -> str:
        links.append(m.group(0))
        return _MD_PLACEHOLDER.format(len(links) - 1)

    return _MD_LINK_RE.sub(_keep, text), links


def _canonicalize_md_link_urls(text: str) -> str:
    from public_assistant.services.public_paths import canonical_public_path

    def _fix(m: re.Match[str]) -> str:
        label, url = m.group(1), canonical_public_path(m.group(2).strip())
        if not is_allowed_public_link(url):
            return label
        return f'[{label}]({url})'

    return _MD_LINK_RE.sub(_fix, text)


def _restore_markdown_links(text: str, links: list[str]) -> str:
    canon_links = [_canonicalize_md_link_urls(raw) for raw in links]
    for i, raw in enumerate(canon_links):
        text = text.replace(_MD_PLACEHOLDER.format(i), raw)
    return text


def _path_to_md(path: str, prefix_label: str | None = None) -> str:
    path = path.strip()
    if not is_allowed_public_link(path):
        return path
    label = prefix_label or label_for_path(path)
    return md_link(label, path)


def normalize_public_answer_links(text: str) -> str:
    """تبدیل مسیرهای خام و backtick به لینک مارک‌داون مجاز."""
    from public_assistant.services.public_paths import canonical_public_path

    if not text:
        return text
    cleaned = _HTML_TAG_RE.sub('', text)
    protected, saved = _protect_markdown_links(cleaned)

    def _fix_bare_contact_us(m: re.Match[str]) -> str:
        return canonical_public_path(m.group(0))

    protected = re.sub(r'/contact-us/?', _fix_bare_contact_us, protected, flags=re.I)

    def prefix_repl(m: re.Match[str]) -> str:
        prefix = m.group('prefix')
        path = m.group('path')
        if prefix == 'راهنما':
            return _path_to_md(path, 'راهنمای فعال‌سازی لایسنس')
        if 'آژانس' in prefix:
            return _path_to_md(path, 'خرید اشتراک آژانس')
        if prefix == 'خرید رسمی':
            link = md_link(label_for_path(path), path)
            return f'برای خرید و فعال‌سازی، {link} را ببینید.'
        return _path_to_md(path, label_for_path(path))

    protected = _PREFIX_PATH_RE.sub(prefix_repl, protected)

    protected = _BACKTICK_PATH_RE.sub(lambda m: _path_to_md(m.group(1)), protected)

    def inline_tick(m: re.Match[str]) -> str:
        lead = m.group('lead')
        path = m.group('path')
        trail = m.group('trail') or ''
        if 'هماهنگ' in lead or 'پشتیبانی' in lead:
            lbl = 'تماس با پشتیبانی' if '/contact/' in path else label_for_path(path)
            return f'{lead}{md_link(lbl, path)}{trail}'
        return f'{lead}{_path_to_md(path)}{trail}'

    protected = _INLINE_BACKTICK_PATH_RE.sub(inline_tick, protected)

    protected = _BARE_PATH_LINE_RE.sub(lambda m: _path_to_md(m.group('path')), protected)

    return _restore_markdown_links(protected, saved)


LINK_STYLE_PROMPT = """
در پاسخ نهایی، لینک‌های رسمی سایت را فقط به‌صورت متن فارسی لینک‌دار نمایش بده:
[عنوان فارسی](/مسیر/)

هرگز مسیر خام URL را به‌جای عنوان لینک ننویس و از backtick برای مسیر استفاده نکن.
به‌جای «خرید رسمی: /products/...» بنویس: [خرید اشتراک](/products/divar-extraction-bot/buy/)
لینک‌ها را طبیعی در جمله بگنجان؛ از ساخت آدرس جدید یا تأییدنشده خودداری کن.
"""
