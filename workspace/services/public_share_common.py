"""ابزارهای مشترک اشتراک عمومی آگهی و فایل شخصی."""
from __future__ import annotations

import re
import secrets
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote, urlparse

from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe

from workspace.mixins import get_or_create_settings
from workspace.models import WorkspaceSettings

DEFAULT_SHARE_MESSAGE_TEMPLATE = (
    'سلام،\n'
    'جزئیات «{title}» را در این لینک ببینید:\n'
    '{url}\n'
    'با تشکر مشاور شما'
)

# شبکه‌های اجتماعی پشتیبانی‌شده در کارت مشاور / مودال اشتراک
SOCIAL_NETWORK_DEFS: Tuple[Dict[str, str], ...] = (
    {
        'key': 'telegram',
        'label': 'تلگرام',
        'icon': 'fab fa-telegram',
        'placeholder': '@username یا ۰۹۱۲…',
        'color': '#229ED9',
        'base': 'https://t.me/',
        'hosts': ('t.me', 'telegram.me', 'telegram.org'),
    },
    {
        'key': 'bale',
        'label': 'بله',
        'icon': 'fas fa-comment-dots',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#00ADEF',
        'base': 'https://ble.ir/',
        'hosts': ('ble.ir', 'bale.ai'),
    },
    {
        'key': 'rubika',
        'label': 'روبیکا',
        'icon': 'fas fa-comments',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#7B2D8E',
        'base': 'https://rubika.ir/',
        'hosts': ('rubika.ir',),
    },
    {
        'key': 'eitaa',
        'label': 'ایتا',
        'icon': 'fas fa-paper-plane',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#F7941D',
        'base': 'https://eitaa.com/',
        'hosts': ('eitaa.com',),
    },
    {
        'key': 'instagram',
        'label': 'اینستاگرام',
        'icon': 'fab fa-instagram',
        'placeholder': '@username',
        'color': '#E4405F',
        'base': 'https://instagram.com/',
        'hosts': ('instagram.com', 'www.instagram.com', 'instagr.am'),
    },
    {
        'key': 'soroush',
        'label': 'سروش',
        'icon': 'fas fa-mobile-alt',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#00A651',
        'base': 'https://splus.ir/',
        'hosts': ('splus.ir', 'sapp.ir'),
    },
)

_SOCIAL_BY_KEY = {d['key']: d for d in SOCIAL_NETWORK_DEFS}

_ALLOWED_WELCOME_TAGS = frozenset({
    'b', 'strong', 'i', 'em', 'u', 'br', 'p', 'ul', 'ol', 'li', 'a', 'span', 'div',
})
_ALLOWED_A_ATTRS = frozenset({'href', 'title', 'rel', 'target'})

# فیلدهای فنی / داخلی — فقط برای منطق داخلی؛ در صفحه عمومی نمایش داده نشوند
PUBLIC_TECHNICAL_KEY_MARKERS = (
    'عرض جغرافیایی', 'طول جغرافیایی', 'latitude', 'longitude',
    'نوع مختصات', 'در شعاع', 'مختصات', 'radius',
    'تعداد تصاویر', 'ویدیو', 'video', 'images_count',
    'ثبت‌شده از دیوار', 'منبع داده',
    'شناسه', 'token', 'لینک', 'link', 'share_link', 'url',
    'تماس', 'phone', 'تلفن', 'موبایل', 'شماره تماس', 'contact_uuid',
    'contact', 'chat', 'چت',
    'تاریخ ایجاد', 'تاریخ انتشار', 'تاریخ انقضا',
    'created_at', 'published_at', 'expires_at',
    'نوع آگهی‌دهنده', 'نوع آگهی دهنده', 'advertiser',
)

# کلیدهایی که در هدر/کارت مالی/مشخصات کلیدی آمده‌اند و نباید در تب‌ها تکرار شوند
PUBLIC_HERO_DEDUP_KEY_MARKERS = (
    'ودیعه', 'deposit', 'رهن', 'اجاره', 'rent', 'قیمت', 'price',
    'قیمت هر متر', 'قیمت/متر', 'متراژ', 'area', 'اتاق', 'rooms',
    'خواب', 'طبقه', 'floor', 'سال ساخت', 'build_year', 'سن بنا',
    'توضیحات', 'description', 'متن آگهی',
)


def generate_share_token() -> str:
    return secrets.token_urlsafe(9)


def unique_share_token(model_cls) -> str:
    token = generate_share_token()
    while model_cls.objects.filter(share_token=token).exists():
        token = generate_share_token()
    return token


class _WelcomeHTMLSanitizer(HTMLParser):
    """سانیتایزر سبک برای پیام خوش‌آمد — فقط تگ‌های امن قالب‌بندی."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out: List[str] = []
        self._stack: List[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'br':
            self._out.append('<br>')
            return
        if tag not in _ALLOWED_WELCOME_TAGS:
            return
        safe_attrs = []
        if tag == 'a':
            href = ''
            for k, v in attrs:
                k = (k or '').lower()
                if k not in _ALLOWED_A_ATTRS or not v:
                    continue
                if k == 'href':
                    href = self._safe_href(v)
                    if not href:
                        return
                    safe_attrs.append(f'href="{href}"')
                elif k == 'title':
                    safe_attrs.append(f'title="{_escape_attr(v)}"')
            safe_attrs.append('rel="noopener noreferrer"')
            safe_attrs.append('target="_blank"')
        attr_str = (' ' + ' '.join(safe_attrs)) if safe_attrs else ''
        self._out.append(f'<{tag}{attr_str}>')
        self._stack.append(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('br',) or tag not in _ALLOWED_WELCOME_TAGS:
            return
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
            self._out.append(f'</{tag}>')

    def handle_data(self, data):
        self._out.append(_escape_text(data))

    def handle_entityref(self, name):
        self._out.append(f'&{name};')

    def handle_charref(self, name):
        self._out.append(f'&#{name};')

    @staticmethod
    def _safe_href(url: str) -> str:
        u = (url or '').strip()
        if not u:
            return ''
        parsed = urlparse(u)
        if parsed.scheme.lower() in ('http', 'https', 'tel', 'mailto'):
            return _escape_attr(u)
        if u.startswith('/') and not u.startswith('//'):
            return _escape_attr(u)
        return ''

    def result(self) -> str:
        while self._stack:
            self._out.append(f'</{self._stack.pop()}>')
        return ''.join(self._out)


def _escape_text(s: str) -> str:
    return (
        (s or '')
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _escape_attr(s: str) -> str:
    return (
        (s or '')
        .replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def sanitize_welcome_html(raw: str) -> str:
    """پاک‌سازی HTML پیام خوش‌آمد برای ذخیره و نمایش امن."""
    text = (raw or '').strip()
    if not text:
        return ''
    # اگر فقط متن ساده است، خط‌ها را به <br> تبدیل کن
    if '<' not in text:
        return '<br>'.join(_escape_text(line) for line in text.splitlines())
    parser = _WelcomeHTMLSanitizer()
    try:
        parser.feed(text)
        parser.close()
    except Exception:
        return _escape_text(re.sub(r'<[^>]+>', '', text))
    return parser.result().strip()


def welcome_html_to_plain(html: str) -> str:
    """نسخه متنی ساده از پیام خوش‌آمد (برای API / پیش‌نمایش)."""
    if not html:
        return ''
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.I)
    text = re.sub(r'</p\s*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = (
        text.replace('&nbsp;', ' ')
        .replace('&amp;', '&')
        .replace('&lt;', '<')
        .replace('&gt;', '>')
        .replace('&quot;', '"')
    )
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _to_english_digits(value: str) -> str:
    table = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
    return (value or '').translate(table)


def _social_phone_digits(value: str) -> str:
    """استخراج شماره موبایل ایران به‌صورت ۹xxxxxxxxx؛ در غیر این صورت خالی."""
    raw = _to_english_digits(value or '')
    digits = re.sub(r'\D', '', raw)
    if not digits:
        return ''
    if digits.startswith('0098'):
        digits = digits[4:]
    elif digits.startswith('98') and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith('0'):
        digits = digits[1:]
    if len(digits) == 10 and digits.startswith('9'):
        return digits
    return ''


def _looks_like_phone(value: str) -> bool:
    raw = _to_english_digits((value or '').strip())
    if not raw:
        return False
    # اگر حرف داشته باشد شماره نیست (مگر + و فاصله و خط تیره)
    if re.search(r'[A-Za-zآ-ی]', raw):
        return False
    return bool(_social_phone_digits(raw))


def _clean_social_username(value: str) -> str:
    u = (value or '').strip().lstrip('@').strip().strip('/')
    u = u.split('?')[0].split('#')[0].strip()
    if not u or len(u) > 64:
        return ''
    # فقط کاراکترهای رایج آیدی
    if not re.fullmatch(r'[A-Za-z0-9_.]+', u):
        return ''
    return u


def _extract_id_from_social_url(network_key: str, url: str) -> str:
    """از لینک کامل، آیدی یا شماره را برای نمایش در فرم برمی‌گرداند."""
    defn = _SOCIAL_BY_KEY.get(network_key) or {}
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = (parsed.netloc or '').lower().removeprefix('www.')
    path = (parsed.path or '').strip('/')
    # tg://resolve?phone=98912...
    if parsed.scheme == 'tg' and 'phone=' in (parsed.query or ''):
        m = re.search(r'phone=(\d+)', parsed.query)
        if m:
            digits = m.group(1)
            if digits.startswith('98') and len(digits) >= 12:
                digits = digits[2:]
            if len(digits) == 10:
                return '0' + digits
            return digits
    hosts = defn.get('hosts') or ()
    if host in hosts or any(host.endswith('.' + h) for h in hosts):
        part = path.split('/')[0] if path else ''
        if part.startswith('+') and _looks_like_phone(part):
            digits = _social_phone_digits(part)
            return f'0{digits}' if digits else part
        return part.lstrip('@') if part else url
    return url


def resolve_social_href(network_key: str, raw: str) -> str:
    """تبدیل آیدی / شماره / لینک به آدرس قابل‌کلیک."""
    value = (raw or '').strip()
    if not value:
        return ''
    defn = _SOCIAL_BY_KEY.get(network_key)
    if not defn:
        return ''

    # لینک کامل یا دامنه بدون scheme
    candidate = value
    if re.match(r'^https?://', candidate, re.I):
        parsed = urlparse(candidate)
        if parsed.scheme.lower() in ('http', 'https') and parsed.netloc:
            return candidate[:500]
    if candidate.startswith('tg://'):
        return candidate[:500]
    if re.match(r'^[a-z0-9.-]+\.[a-z]{2,}(/|$)', candidate, re.I):
        full = 'https://' + candidate.lstrip('/')
        parsed = urlparse(full)
        if parsed.netloc:
            return full[:500]

    # شماره موبایل
    if _looks_like_phone(value):
        digits = _social_phone_digits(value)
        if not digits:
            return ''
        if network_key == 'telegram':
            return f'tg://resolve?phone=98{digits}'
        if network_key == 'instagram':
            # اینستاگرام با شماره پروفایل عمومی ندارد
            return ''
        return f"{defn['base']}{digits}"

    # آیدی / یوزرنیم خالی
    username = _clean_social_username(value)
    if not username:
        return ''
    return f"{defn['base']}{username}"


def normalize_social_value(network_key: str, raw: str) -> str:
    """
    مقدار ذخیره‌شده در تنظیمات:
    - لینک کامل → همان لینک نرمال
    - آیدی → آیدی بدون @
    - شماره → 09xxxxxxxxx
    """
    value = (raw or '').strip()
    if not value:
        return ''

    # اگر لینک کامل است، برای فرم آیدی/شماره را استخراج کن تا دوباره لینک کامل نماند
    if re.match(r'^https?://', value, re.I) or value.startswith('tg://') or re.match(
        r'^[a-z0-9.-]+\.[a-z]{2,}(/|$)', value, re.I,
    ):
        href = resolve_social_href(network_key, value)
        if not href:
            return ''
        extracted = _extract_id_from_social_url(network_key, href)
        # اگر استخراج نشد، خود لینک را نگه دار
        return (extracted or href)[:200]

    if _looks_like_phone(value):
        if network_key == 'instagram':
            return ''
        digits = _social_phone_digits(value)
        return f'0{digits}' if digits else ''

    username = _clean_social_username(value)
    return username[:64]


def normalize_social_url(url: str, network_key: str = '') -> str:
    """سازگاری با نام قبلی — خروجی لینک قابل‌کلیک است."""
    if network_key:
        return resolve_social_href(network_key, url)
    # بدون کلید شبکه: فقط لینک کامل را بپذیر
    u = (url or '').strip()
    if not u:
        return ''
    if not re.match(r'^https?://', u, re.I):
        if re.match(r'^[a-z0-9.-]+\.[a-z]{2,}(/|$)', u, re.I):
            u = 'https://' + u.lstrip('/')
        else:
            return ''
    parsed = urlparse(u)
    if parsed.scheme.lower() not in ('http', 'https'):
        return ''
    if not parsed.netloc:
        return ''
    return u[:500]


def normalize_social_links(raw) -> Dict[str, str]:
    """استخراج و نرمال‌سازی مقادیر اجتماعی (آیدی / شماره / لینک)."""
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, str] = {}
    for defn in SOCIAL_NETWORK_DEFS:
        key = defn['key']
        val = normalize_social_value(key, str(src.get(key) or ''))
        if val:
            out[key] = val
    return out


def social_links_from_post(post) -> Dict[str, str]:
    raw = {}
    for defn in SOCIAL_NETWORK_DEFS:
        key = defn['key']
        raw[key] = post.get(f'social_{key}') or post.get(key) or ''
    return normalize_social_links(raw)


def social_networks_for_display(links: Optional[dict]) -> List[Dict[str, str]]:
    """لیست شبکه‌های دارای لینک برای رندر در UI عمومی."""
    links = links or {}
    items: List[Dict[str, str]] = []
    for defn in SOCIAL_NETWORK_DEFS:
        raw = (links.get(defn['key']) or '').strip()
        if not raw:
            continue
        href = resolve_social_href(defn['key'], raw)
        if not href:
            continue
        items.append({
            'key': defn['key'],
            'label': defn['label'],
            'icon': defn['icon'],
            'color': defn['color'],
            'url': href,
            'value': raw,
        })
    return items


def get_share_message_template(user) -> str:
    ws = get_or_create_settings(user)
    tpl = (ws.default_share_message or '').strip()
    return tpl or DEFAULT_SHARE_MESSAGE_TEMPLATE


def render_share_message(template: str, *, title: str, url: str) -> str:
    tpl = (template or '').strip() or DEFAULT_SHARE_MESSAGE_TEMPLATE
    safe_title = (title or 'ملک').strip() or 'ملک'
    safe_url = (url or '').strip()
    return (
        tpl.replace('{title}', safe_title)
        .replace('{url}', safe_url)
        .replace('{TITLE}', safe_title)
        .replace('{URL}', safe_url)
    )


def resolve_welcome_message(user, share) -> Dict[str, Any]:
    """پیام خوش‌آمد مؤثر: سفارشی فایل یا پیش‌فرض پروفایل."""
    ws = get_or_create_settings(user)
    stored = (share.welcome_message or '').strip()
    default = (ws.default_welcome_message or '').strip()
    effective_raw = stored or default
    effective = sanitize_welcome_html(effective_raw) if effective_raw else ''
    return {
        'welcome_message': effective,
        'welcome_message_html': mark_safe(effective) if effective else '',
        'welcome_plain': welcome_html_to_plain(effective),
        'is_custom': bool(stored),
        'default_welcome_message': default,
        'from_default': not bool(stored) and bool(default),
    }


def save_share_profile_defaults(
    user,
    *,
    default_share_message: Optional[str] = None,
    default_welcome_message: Optional[str] = None,
    social_links: Optional[dict] = None,
    save_share_message: bool = False,
    save_welcome: bool = False,
    save_socials: bool = False,
) -> WorkspaceSettings:
    """ذخیره پیش‌فرض‌های اشتراک در تنظیمات کاربر."""
    ws = get_or_create_settings(user)
    changed = False
    if save_share_message and default_share_message is not None:
        tpl = (default_share_message or '').strip()
        # اگر کاربر متن رندر‌شده فرستاده، سعی نکن خرابش کنیم — همان قالب را نگه دار
        ws.default_share_message = tpl[:4000]
        changed = True
    if save_welcome and default_welcome_message is not None:
        ws.default_welcome_message = sanitize_welcome_html(default_welcome_message)[:8000]
        changed = True
    if save_socials and social_links is not None:
        ws.social_links = normalize_social_links(social_links)
        changed = True
    if changed:
        ws.save()
    return ws


def apply_share_form_extras(user, post, share) -> Dict[str, Any]:
    """
    پردازش فیلدهای اضافی مودال اشتراک:
    - پیام خوش‌آمد (فایل / پیش‌فرض)
    - متن اشتراک پیش‌فرض
    - لینک شبکه‌های اجتماعی
    """
    welcome_raw = post.get('welcome_message') or ''
    save_as_default_welcome = post.get('save_as_default_welcome') in ('1', 'true', 'on')
    save_as_default_message = post.get('save_as_default_share_message') in ('1', 'true', 'on')
    clear_custom_welcome = post.get('use_default_welcome') in ('1', 'true', 'on')

    socials = social_links_from_post(post)
    save_share_profile_defaults(
        user,
        social_links=socials,
        save_socials=True,
        default_welcome_message=welcome_raw if save_as_default_welcome else None,
        save_welcome=save_as_default_welcome,
        default_share_message=post.get('share_message_template') if save_as_default_message else None,
        save_share_message=save_as_default_message,
    )

    if clear_custom_welcome or save_as_default_welcome:
        # با ذخیره پیش‌فرض، این فایل هم از همان پیش‌فرض پیروی کند
        share.welcome_message = ''
    else:
        cleaned = sanitize_welcome_html(welcome_raw)
        default = (get_or_create_settings(user).default_welcome_message or '').strip()
        # اگر دقیقاً همان پیش‌فرض است، خالی بگذار تا همیشه از پروفایل خوانده شود
        if cleaned and default and cleaned == default:
            share.welcome_message = ''
        else:
            share.welcome_message = cleaned

    return {
        'social_links': socials,
        'welcome_resolved': resolve_welcome_message(user, share),
    }


def share_profile_context(user, share, *, title: str = '', share_url: str = '') -> Dict[str, Any]:
    """کانتکست مشترک مودال اشتراک و پاسخ JSON."""
    ws = get_or_create_settings(user)
    form_vals = share_consultant_form_values(user, share)
    welcome = resolve_welcome_message(user, share)
    msg_tpl = get_share_message_template(user)
    rendered_msg = render_share_message(msg_tpl, title=title, url=share_url)
    socials = normalize_social_links(ws.social_links or {})
    networks = [
        {
            'key': defn['key'],
            'label': defn['label'],
            'icon': defn['icon'],
            'color': defn['color'],
            'placeholder': defn['placeholder'],
            'url': socials.get(defn['key'], ''),
        }
        for defn in SOCIAL_NETWORK_DEFS
    ]
    return {
        **form_vals,
        'welcome_message': welcome['welcome_message'],
        'welcome_is_custom': welcome['is_custom'],
        'welcome_from_default': welcome['from_default'],
        'default_welcome_message': welcome['default_welcome_message'],
        'default_share_message': msg_tpl,
        'share_message_rendered': rendered_msg,
        'social_links': socials,
        'social_networks': networks,
        'social_networks_active': social_networks_for_display(socials),
    }


def profile_consultant_defaults(user) -> tuple[str, str]:
    """نام و شماره پیش‌فرض مشاور از پروفایل / تنظیمات آژانس."""
    settings = get_or_create_settings(user)
    name = (settings.agency_name or '').strip()
    if not name:
        name = (user.get_full_name() or '').strip()
    if not name:
        name = (getattr(user, 'first_name', '') or '').strip()
    phone = (getattr(user, 'phone', '') or '').strip()
    return name, phone


def consultant_name(user, settings: WorkspaceSettings, share) -> str:
    if (share.consultant_name or '').strip():
        return share.consultant_name.strip()
    name, _ = profile_consultant_defaults(user)
    if name:
        return name
    if (settings.agency_name or '').strip():
        return settings.agency_name.strip()
    return 'مشاور املاک'


def consultant_phone(user, share) -> str:
    if (share.consultant_phone or '').strip():
        return share.consultant_phone.strip()
    _, phone = profile_consultant_defaults(user)
    return phone


def share_consultant_form_values(user, share) -> Dict[str, Any]:
    """مقادیر فرم مودال اشتراک — از share یا در صورت خالی از پروفایل."""
    profile_name, profile_phone = profile_consultant_defaults(user)
    stored_name = (share.consultant_name or '').strip()
    stored_phone = (share.consultant_phone or '').strip()
    return {
        'consultant_name': stored_name or profile_name,
        'consultant_phone': stored_phone or profile_phone,
        'from_profile_name': not stored_name,
        'from_profile_phone': not stored_phone,
        'profile_name': profile_name,
        'profile_phone': profile_phone,
    }


def normalize_consultant_fields_for_save(user, name: str, phone: str) -> tuple[str, str]:
    """اگر مقدار همان پروفایل باشد خالی ذخیره می‌شود تا همیشه از پروفایل خوانده شود."""
    profile_name, profile_phone = profile_consultant_defaults(user)
    name = (name or '').strip()[:200]
    phone = (phone or '').strip()[:20]
    if name and name == profile_name:
        name = ''
    if phone and phone == profile_phone:
        phone = ''
    return name, phone


def phone_whatsapp_digits(phone: str) -> str:
    digits = ''.join(c for c in (phone or '') if c.isdigit())
    if digits.startswith('98'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits[1:]
    return digits


def consultant_contact_urls(phone: str, message: str = '') -> Dict[str, str]:
    wa_digits = phone_whatsapp_digits(phone)
    tel = phone.strip() if phone else ''
    urls = {'tel_url': f'tel:{tel}' if tel else '', 'whatsapp_url': ''}
    if wa_digits:
        base = f'https://wa.me/98{wa_digits}'
        urls['whatsapp_url'] = f'{base}?text={quote(message)}' if message else base
    return urls


def absolute_public_share_url(url_name: str, *, share_token: str) -> str:
    """آدرس کامل صفحه عمومی — بدون نیاز به request."""
    path = reverse(url_name, kwargs={'share_token': share_token})
    base = (getattr(settings, 'SITE_URL', '') or '').strip().rstrip('/')
    return f'{base}{path}' if base else path


def public_share_to_dict(share, request, *, url_name: str) -> Dict[str, Any]:
    path = reverse(url_name, kwargs={'share_token': share.share_token})
    share_url = request.build_absolute_uri(path) if request else absolute_public_share_url(url_name, share_token=share.share_token)
    profile = share_profile_context(share.created_by, share, share_url=share_url)
    return {
        'share_url': share_url,
        'share_token': share.share_token,
        'view_count': share.view_count,
        'is_active': share.is_active,
        'consultant_name': profile['consultant_name'],
        'consultant_phone': profile['consultant_phone'],
        'consultant_name_stored': share.consultant_name,
        'consultant_phone_stored': share.consultant_phone,
        'welcome_message': profile['welcome_message'],
        'welcome_is_custom': profile['welcome_is_custom'],
        'default_share_message': profile['default_share_message'],
        'share_message_rendered': profile['share_message_rendered'],
        'social_links': profile['social_links'],
        'show_divar_link': share.show_divar_link,
        'show_full_address': getattr(share, 'show_full_address', False),
        'show_internal_notes': getattr(share, 'show_internal_notes', False),
    }


def build_map_navigation(latitude, longitude) -> Dict[str, Any] | None:
    """لینک مسیریابی برای صفحه عمومی — وقتی مختصات معتبر است."""
    if latitude is None or longitude is None:
        return None
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    if lat == 0 and lng == 0:
        return None
    dest = f'{lat},{lng}'
    return {
        'latitude': lat,
        'longitude': lng,
        'google_url': f'https://www.google.com/maps/dir/?api=1&destination={dest}',
        'neshan_url': f'https://neshan.org/maps/routing/car/destination/{lat},{lng}',
        'waze_url': f'https://waze.com/ul?ll={lat},{lng}&navigate=yes',
    }


def is_public_technical_key(key: str) -> bool:
    """آیا این کلید اطلاعات فنی/داخلی است و نباید در صفحه عمومی بیاید؟"""
    kl = str(key or '').lower()
    return any(m in key or m in kl for m in PUBLIC_TECHNICAL_KEY_MARKERS)


def is_public_hero_dedup_key(key: str) -> bool:
    """کلیدهایی که در بخش‌های بالای صفحه نمایش داده شده‌اند."""
    kl = str(key or '').lower()
    return any(m in key or m in kl for m in PUBLIC_HERO_DEDUP_KEY_MARKERS)


def filter_public_feature_highlights(feature_profile: dict, highlights: list) -> list:
    """برچسب‌های تکراری با feature_profile.core را از نوار highlights حذف می‌کند."""
    skip: set[str] = set()
    for item in feature_profile.get('core', []):
        if not (item.get('known') and item.get('state') == 'yes'):
            continue
        for field in ('label', 'key'):
            val = str(item.get(field) or '').strip()
            if val:
                skip.add(val)
    filtered: list = []
    for text in highlights:
        label = str(text or '').strip()
        if not label:
            continue
        base = label.split(':')[0].replace(' ندارد', '').strip()
        if label in skip or base in skip:
            continue
        filtered.append(label)
    return filtered


def _looks_like_agency_name(name: str) -> bool:
    n = (name or '').strip()
    if not n:
        return False
    markers = ('آژانس', 'املاک', 'مشاورین', 'گروه', 'دفتر')
    return any(m in n for m in markers)


def resolve_consultant_display(user, share) -> Dict[str, Any]:
    """
    نام آژانس و مشاور را بدون تناقض برمی‌گرداند.
    brand_name: نام برند/آژانس برای تاپ‌بار و کارت
    person_name: نام مشاور (فقط اگر با برند متفاوت باشد)
    """
    ws = get_or_create_settings(user)
    agency = (ws.agency_name or '').strip()
    override = (share.consultant_name or '').strip()
    profile_name, _ = profile_consultant_defaults(user)

    if agency and override and override != agency:
        # override شخص مشاور است یا نام آژانس دیگر؟
        if _looks_like_agency_name(override) and _looks_like_agency_name(agency):
            # دو نام آژانس‌مانند — فقط برند تنظیمات را نشان بده
            brand = agency
            person = ''
        else:
            brand = agency
            person = override
    elif agency:
        brand = agency
        person = ''
        # اگر نام پروفایل شخص است و با آژانس فرق دارد
        if profile_name and profile_name != agency and not _looks_like_agency_name(profile_name):
            if override == profile_name or not override:
                person = profile_name
    elif override:
        brand = override
        person = ''
    else:
        brand = profile_name or 'مشاور املاک'
        person = ''

    display_name = person or brand
    return {
        'brand_name': brand,
        'person_name': person,
        'display_name': display_name,
        'agency_name': agency,
        'show_person': bool(person and person != brand),
    }


def build_finance_summary(listing_like, tx: Dict[str, Any], data: Optional[dict] = None) -> Dict[str, Any]:
    """کارت مالی یکپارچه برای صفحه عمومی — بدون تکرار."""
    from workspace.services.formatting import format_toman

    data = data or {}
    items: List[Dict[str, str]] = []
    primary = ''
    note = ''

    def _get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    # قابل تبدیل از داده خام
    for key, val in data.items():
        kl = str(key or '')
        if 'تبدیل' in kl:
            v = str(val or '').strip()
            if v and v.lower() not in ('-', 'nan', 'none', '—'):
                note = v if 'تبدیل' in v else f'قابل تبدیل: {v}'
                break

    price = _get(listing_like, 'price')
    if tx.get('show_price') and price:
        primary = format_toman(price)
        items.append({'label': 'قیمت', 'value': primary, 'kind': 'price'})
        pps = _get(listing_like, 'price_per_sqm')
        if tx.get('show_price_per_sqm') and pps:
            items.append({'label': 'قیمت هر متر', 'value': format_toman(pps, per_sqm=True), 'kind': 'pps'})

    if tx.get('show_deposit'):
        deposit = _get(listing_like, 'deposit')
        if deposit:
            dep_label = format_toman(deposit)
            items.append({'label': 'ودیعه', 'value': dep_label, 'kind': 'deposit'})
            if not primary:
                primary = f'ودیعه {dep_label}'
        elif data:
            from workspace.services.display import _listing_text_deposit
            txt = _listing_text_deposit(data)
            if txt:
                items.append({'label': 'ودیعه', 'value': txt, 'kind': 'deposit'})
                if not primary:
                    primary = txt if txt in ('متعارف', 'توافقی') else f'ودیعه {txt}'

    if tx.get('show_rent'):
        rent = _get(listing_like, 'rent')
        if rent is not None and rent != '':
            try:
                rent_num = float(rent)
            except (TypeError, ValueError):
                rent_num = None
            if rent_num is not None and rent_num == 0:
                items.append({'label': 'اجاره ماهانه', 'value': 'بدون اجاره', 'kind': 'rent'})
                if not note and tx.get('show_deposit'):
                    note = 'رهن کامل'
            elif rent_num is not None and rent_num > 0:
                rent_label = format_toman(rent_num)
                items.append({'label': 'اجاره ماهانه', 'value': rent_label, 'kind': 'rent'})
                if not primary:
                    primary = f'اجاره {rent_label}'
            elif rent_num is None:
                from workspace.services.display import _listing_text_rent
                txt = _listing_text_rent(data)
                if txt:
                    items.append({'label': 'اجاره ماهانه', 'value': txt, 'kind': 'rent'})
        elif data:
            from workspace.services.display import _listing_text_rent
            txt = _listing_text_rent(data)
            if txt:
                items.append({'label': 'اجاره ماهانه', 'value': txt, 'kind': 'rent'})

    # اگر فقط ودیعه داریم و اجاره در داده نیست ولی معامله اجاره‌ای است
    if tx.get('show_rent') and not any(i['kind'] == 'rent' for i in items):
        deposit = _get(listing_like, 'deposit')
        rent = _get(listing_like, 'rent')
        if deposit and (rent in (None, 0, 0.0, '')):
            items.append({'label': 'اجاره ماهانه', 'value': 'بدون اجاره', 'kind': 'rent'})
            if not note:
                note = 'رهن کامل'

    return {
        'items': items,
        'primary': primary,
        'note': note,
        'has_finance': bool(items or primary),
    }


def count_active_files(user) -> int:
    """تعداد فایل/آگهی فعال کاربر برای کارت مشاور."""
    try:
        from workspace.models import Listing
        n = Listing.objects.filter(
            dataset__user=user,
            dataset__is_active=True,
        ).count()
        try:
            from workspace.models import CRMProperty
            n += CRMProperty.objects.filter(
                user=user,
                deleted_at__isnull=True,
                transaction_status='فعال',
            ).count()
        except Exception:
            pass
        return n
    except Exception:
        return 0


def build_consultant_block(user, share, *, title: str = 'ملک') -> Dict[str, Any]:
    ws = get_or_create_settings(user)
    display = resolve_consultant_display(user, share)
    phone = consultant_phone(user, share)
    greet_name = display['person_name'] or display['brand_name']
    wa_message = f'سلام {greet_name}، درباره «{title}» اطلاعات بیشتری می‌خواهم.'
    active_count = count_active_files(user)
    welcome = resolve_welcome_message(user, share)
    socials = normalize_social_links(ws.social_links or {})
    social_items = social_networks_for_display(socials)
    return {
        'name': display['display_name'],
        'brand_name': display['brand_name'],
        'person_name': display['person_name'],
        'show_person': display['show_person'],
        'phone': phone,
        'phone_display': phone,
        'has_phone': bool(phone),
        'agency_name': display['agency_name'] or display['brand_name'],
        'agency_logo': ws.agency_logo,
        'welcome_message': welcome['welcome_plain'] or welcome_html_to_plain(welcome['welcome_message']),
        'welcome_message_html': welcome['welcome_message_html'],
        'has_welcome': bool(welcome['welcome_message']),
        'social_links': socials,
        'social_networks': social_items,
        'has_socials': bool(social_items),
        'active_files_count': active_count,
        'is_verified': bool(ws.agency_name and ws.agency_logo),
        **consultant_contact_urls(phone, wa_message),
    }


def strip_duplicate_section_fields(
    sections: Dict[str, Dict[str, str]],
    *,
    also_hide_description: bool = True,
) -> Dict[str, Dict[str, str]]:
    """حذف فیلدهای تکراری و فنی از سکشن‌های جزئیات عمومی."""
    result: Dict[str, Dict[str, str]] = {}
    seen_normalized: Set[str] = set()

    def _norm(k: str) -> str:
        return str(k or '').strip().lower().replace(' ', '').replace('_', '').replace('‌', '')

    for name, fields in sections.items():
        cleaned: Dict[str, str] = {}
        for key, val in (fields or {}).items():
            if is_public_technical_key(key):
                continue
            if is_public_hero_dedup_key(key):
                continue
            if key.strip() in ('ساخت', 'سال ساخت'):
                continue
            if also_hide_description and any(m in key for m in ('توضیح', 'description', 'متن آگهی')):
                continue
            nk = _norm(key)
            # ادغام «سال ساخت» و «ساخت»
            if nk in ('سالساخت', 'ساخت', 'buildyear', 'سنبنا'):
                continue
            if nk in seen_normalized:
                continue
            # ودیعه تکراری با برچسب‌های مختلف
            if any(m in key for m in ('ودیعه', 'رهن', 'deposit')) and 'ودیعه' in seen_normalized:
                continue
            seen_normalized.add(nk)
            if any(m in key for m in ('ودیعه', 'رهن', 'deposit')):
                seen_normalized.add('ودیعه')
            cleaned[key] = val
        if cleaned:
            result[name] = cleaned
    return result


def remap_public_section_labels(sections: Dict[str, Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """برچسب تب‌ها را به دسته‌بندی پیشنهادی صفحه عمومی نزدیک می‌کند."""
    label_map = {
        'مالی': 'شرایط مالی',
        'ملک': 'مشخصات اصلی',
        'مکان': 'موقعیت مکانی',
        'متن': 'توضیحات',
    }
    result: Dict[str, Dict[str, str]] = {}
    for name, fields in sections.items():
        result[label_map.get(name, name)] = fields
    return result
