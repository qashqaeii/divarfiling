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
        'icon_file': 'icons/telegram.png',
        'placeholder': '@username یا ۰۹۱۲…',
        'color': '#2AABEE',
        'base': 'https://t.me/',
        'hosts': ('t.me', 'telegram.me', 'telegram.org'),
    },
    {
        'key': 'bale',
        'label': 'بله',
        'icon': 'fas fa-comment-dots',
        'icon_file': 'icons/bale.png',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#00C2A8',
        'base': 'https://ble.ir/',
        'hosts': ('ble.ir', 'bale.ai'),
    },
    {
        'key': 'rubika',
        'label': 'روبیکا',
        'icon': 'fas fa-comments',
        'icon_file': 'icons/rubika.png',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#6C2BD9',
        'base': 'https://rubika.ir/',
        'hosts': ('rubika.ir',),
    },
    {
        'key': 'eitaa',
        'label': 'ایتا',
        'icon': 'fas fa-paper-plane',
        'icon_file': 'icons/eita.png',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#F7941D',
        'base': 'https://eitaa.com/',
        'hosts': ('eitaa.com',),
    },
    {
        'key': 'instagram',
        'label': 'اینستاگرام',
        'icon': 'fab fa-instagram',
        'icon_file': 'icons/Instagram.png',
        'placeholder': '@username',
        'color': '#E1306C',
        'base': 'https://instagram.com/',
        'hosts': ('instagram.com', 'www.instagram.com', 'instagr.am'),
    },
    {
        'key': 'soroush',
        'label': 'سروش',
        'icon': 'fas fa-mobile-alt',
        'icon_file': 'icons/sorosh.png',
        'placeholder': 'آیدی یا ۰۹۱۲…',
        'color': '#1E6BFF',
        'base': 'https://splus.ir/',
        'hosts': ('splus.ir', 'sapp.ir'),
    },
)

WHATSAPP_ICON_FILE = 'icons/whatsup.png'

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
    'آگهی‌های فعال مشاور', 'آگهی های فعال مشاور', 'مشاور_آگهی_فعال',
    'آگهی فعال مشاور', 'تعداد آگهی فعال',
    'نام مشاور / آژانس', 'نام مشاور/آژانس', 'مشاور_نام',
    'نام آژانس', 'نام مشاور', 'consultant_name', 'agency_name',
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


def social_links_from_post(post, *, prefix: str = 'social_') -> Dict[str, str]:
    """خواندن سوشال از POST؛ prefix پیش‌فرض social_ و برای دفتر agency_social_."""
    raw = {}
    for defn in SOCIAL_NETWORK_DEFS:
        key = defn['key']
        raw[key] = post.get(f'{prefix}{key}') or (post.get(key) if prefix == 'social_' else '') or ''
    return normalize_social_links(raw)


def agency_social_links_from_post(post) -> Dict[str, str]:
    return social_links_from_post(post, prefix='agency_social_')


def social_networks_form_list(links: Optional[dict]) -> List[Dict[str, str]]:
    """لیست شبکه‌ها برای فرم‌های تنظیمات / مودال / داشبورد."""
    return _social_networks_form_list(links)


def _social_networks_form_list(links: Optional[dict]) -> List[Dict[str, str]]:
    socials = normalize_social_links(links or {})
    return [
        {
            'key': defn['key'],
            'label': defn['label'],
            'icon': defn['icon'],
            'icon_file': defn.get('icon_file', ''),
            'color': defn['color'],
            'placeholder': defn['placeholder'],
            'url': socials.get(defn['key'], ''),
        }
        for defn in SOCIAL_NETWORK_DEFS
    ]


def normalize_agency_website(raw: str) -> str:
    url = (raw or '').strip()
    if not url:
        return ''
    if not re.match(r'^https?://', url, re.I):
        if re.match(r'^[a-z0-9.-]+\.[a-z]{2,}(/|$)', url, re.I):
            url = 'https://' + url.lstrip('/')
        else:
            return ''
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc:
        return ''
    return url[:500]


def parse_optional_float(raw) -> Optional[float]:
    text = str(raw or '').strip().replace(',', '.')
    if not text:
        return None
    try:
        val = float(text)
    except (TypeError, ValueError):
        return None
    return val


def landline_tel_url(phone: str) -> str:
    tel = (phone or '').strip()
    if not tel:
        return ''
    digits = ''.join(c for c in tel if c.isdigit() or c == '+')
    return f'tel:{digits or tel}'


def _media_url_or_none(field) -> Optional[str]:
    if not field:
        return None
    try:
        return field.url
    except (ValueError, AttributeError):
        return None


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
            'icon_file': defn.get('icon_file', ''),
            'color': defn['color'],
            'url': href,
            'value': raw,
        })
    return items


def build_share_send_channels(social_links: Optional[dict] = None) -> List[Dict[str, str]]:
    """
    دکمه‌های «ارسال متن» زیر پیش‌نمایش مودال اشتراک.
    واتساپ همیشه هست؛ بقیه فقط برای شبکه‌هایی که در پروفایل ذخیره شده‌اند.
    """
    channels: List[Dict[str, str]] = [
        {
            'key': 'whatsapp',
            'label': 'واتساپ',
            'icon_file': WHATSAPP_ICON_FILE,
            'color': '#25D366',
            'mode': 'whatsapp',
            'href': '',
        },
    ]
    for item in social_networks_for_display(social_links):
        key = item['key']
        if key == 'telegram':
            mode = 'telegram'
        else:
            # بله / روبیکا / ایتا / سروش / اینستاگرام: کپی متن + باز کردن پروفایل
            mode = 'copy_open'
        channels.append({
            'key': key,
            'label': item['label'],
            'icon_file': item.get('icon_file', ''),
            'color': item.get('color', '#64748b'),
            'mode': mode,
            'href': item.get('url', ''),
        })
    return channels


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
    agency_social_links: Optional[dict] = None,
    save_share_message: bool = False,
    save_welcome: bool = False,
    save_socials: bool = False,
    save_agency_socials: bool = False,
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
    if save_agency_socials and agency_social_links is not None:
        ws.agency_social_links = normalize_social_links(agency_social_links)
        changed = True
    if changed:
        ws.save()
    return ws


def apply_agency_profile_fields(ws: WorkspaceSettings, post, files=None) -> list[str]:
    """اعمال فیلدهای پروفایل دفتر/مشاور روی WorkspaceSettings؛ لیست فیلدهای تغییر‌یافته."""
    changed: list[str] = []

    def _set_char(attr: str, value: str, *, maxlen: int):
        cleaned = (value or '').strip()[:maxlen]
        if getattr(ws, attr) != cleaned:
            setattr(ws, attr, cleaned)
            changed.append(attr)

    _set_char('agency_address', post.get('agency_address') or '', maxlen=2000)
    _set_char('agency_city', post.get('agency_city') or '', maxlen=100)
    _set_char('agency_landline', post.get('agency_landline') or '', maxlen=32)
    _set_char('agency_landline_alt', post.get('agency_landline_alt') or '', maxlen=32)

    website = normalize_agency_website(post.get('agency_website') or '')
    if ws.agency_website != website:
        ws.agency_website = website
        changed.append('agency_website')

    lat = parse_optional_float(post.get('agency_latitude'))
    lng = parse_optional_float(post.get('agency_longitude'))
    if lat is not None and not (-90 <= lat <= 90):
        lat = None
    if lng is not None and not (-180 <= lng <= 180):
        lng = None
    if ws.agency_latitude != lat:
        ws.agency_latitude = lat
        changed.append('agency_latitude')
    if ws.agency_longitude != lng:
        ws.agency_longitude = lng
        changed.append('agency_longitude')

    files = files or {}
    photo = files.get('consultant_photo') if hasattr(files, 'get') else None
    card = files.get('business_card_image') if hasattr(files, 'get') else None
    if photo:
        ws.consultant_photo = photo
        changed.append('consultant_photo')
    if card:
        ws.business_card_image = card
        changed.append('business_card_image')
    if post.get('clear_consultant_photo') in ('1', 'true', 'on'):
        if ws.consultant_photo:
            ws.consultant_photo.delete(save=False)
            ws.consultant_photo = None
            changed.append('consultant_photo')
    if post.get('clear_business_card_image') in ('1', 'true', 'on'):
        if ws.business_card_image:
            ws.business_card_image.delete(save=False)
            ws.business_card_image = None
            changed.append('business_card_image')

    return changed


def apply_share_form_extras(user, post, share, files=None) -> Dict[str, Any]:
    """
    پردازش فیلدهای اضافی مودال اشتراک:
    - پیام خوش‌آمد (فایل / پیش‌فرض)
    - متن اشتراک پیش‌فرض
    - لینک شبکه‌های اجتماعی مشاور و دفتر
    - پروفایل دفتر (آدرس، تلفن، مختصات، تصاویر)
    """
    welcome_raw = post.get('welcome_message') or ''
    save_as_default_welcome = post.get('save_as_default_welcome') in ('1', 'true', 'on')
    save_as_default_message = post.get('save_as_default_share_message') in ('1', 'true', 'on')
    clear_custom_welcome = post.get('use_default_welcome') in ('1', 'true', 'on')

    socials = social_links_from_post(post)
    has_agency_social_fields = any(
        f'agency_social_{defn["key"]}' in post for defn in SOCIAL_NETWORK_DEFS
    )
    agency_socials = agency_social_links_from_post(post) if has_agency_social_fields else None
    save_share_profile_defaults(
        user,
        social_links=socials,
        agency_social_links=agency_socials,
        save_socials=True,
        save_agency_socials=has_agency_social_fields,
        default_welcome_message=welcome_raw if save_as_default_welcome else None,
        save_welcome=save_as_default_welcome,
        default_share_message=post.get('share_message_template') if save_as_default_message else None,
        save_share_message=save_as_default_message,
    )

    profile_field_keys = (
        'agency_address', 'agency_city', 'agency_landline', 'agency_landline_alt',
        'agency_website', 'agency_latitude', 'agency_longitude',
        'clear_consultant_photo', 'clear_business_card_image',
    )
    has_profile_fields = any(k in post for k in profile_field_keys)
    has_profile_files = bool(
        files and hasattr(files, 'get') and (
            files.get('consultant_photo') or files.get('business_card_image')
        )
    )
    if has_profile_fields or has_profile_files:
        ws = get_or_create_settings(user)
        profile_changed = apply_agency_profile_fields(ws, post, files)
        if profile_changed:
            ws.save(update_fields=[*profile_changed, 'updated_at'])

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
        'agency_social_links': agency_socials or {},
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
    agency_socials = normalize_social_links(ws.agency_social_links or {})
    networks = _social_networks_form_list(socials)
    agency_networks = _social_networks_form_list(agency_socials)
    photo_url = _media_url_or_none(ws.consultant_photo)
    card_url = _media_url_or_none(ws.business_card_image)
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
        'agency_social_links': agency_socials,
        'agency_social_networks': agency_networks,
        'agency_social_networks_active': social_networks_for_display(agency_socials),
        'share_send_channels': build_share_send_channels(socials),
        'whatsapp_icon_file': WHATSAPP_ICON_FILE,
        'telegram_icon_file': _SOCIAL_BY_KEY['telegram']['icon_file'],
        'agency_address': (ws.agency_address or '').strip(),
        'agency_city': (ws.agency_city or '').strip(),
        'agency_landline': (ws.agency_landline or '').strip(),
        'agency_landline_alt': (ws.agency_landline_alt or '').strip(),
        'agency_website': (ws.agency_website or '').strip(),
        'agency_latitude': ws.agency_latitude if ws.agency_latitude is not None else '',
        'agency_longitude': ws.agency_longitude if ws.agency_longitude is not None else '',
        'consultant_photo_url': photo_url,
        'business_card_url': card_url,
        'agency_name_profile': (ws.agency_name or '').strip(),
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
        'balad_url': f'https://balad.ir/directions?destination={dest}',
    }


def build_agency_office_block(ws: WorkspaceSettings) -> Dict[str, Any]:
    """بلوک اطلاعات دفتر املاک برای کارت مشاور صفحه عمومی."""
    address = (ws.agency_address or '').strip()
    city = (ws.agency_city or '').strip()
    landline = (ws.agency_landline or '').strip()
    landline_alt = (ws.agency_landline_alt or '').strip()
    website = (ws.agency_website or '').strip()
    agency_socials = normalize_social_links(ws.agency_social_links or {})
    agency_social_items = social_networks_for_display(agency_socials)
    map_nav = build_map_navigation(ws.agency_latitude, ws.agency_longitude)
    landlines = []
    if landline:
        landlines.append({
            'label': landline,
            'display': landline,
            'tel_url': landline_tel_url(landline),
        })
    if landline_alt:
        landlines.append({
            'label': landline_alt,
            'display': landline_alt,
            'tel_url': landline_tel_url(landline_alt),
        })
    address_line = address
    if city and city not in address:
        address_line = f'{address}، {city}'.strip('، ') if address else city
    return {
        'address': address,
        'city': city,
        'address_line': address_line,
        'has_address': bool(address_line),
        'landline': landline,
        'landline_alt': landline_alt,
        'landlines': landlines,
        'has_landlines': bool(landlines),
        'website': website,
        'has_website': bool(website),
        'latitude': ws.agency_latitude,
        'longitude': ws.agency_longitude,
        'map_navigation': map_nav,
        'has_map_navigation': bool(map_nav),
        'social_links': agency_socials,
        'social_networks': agency_social_items,
        'has_socials': bool(agency_social_items),
    }


def _normalize_public_key(key: str) -> str:
    """نرمال‌سازی کلید برای تطبیق پایدار (ZWNJ، فاصله، ی/ک عربی)."""
    text = str(key or '').strip().lower()
    for ch in ('\u200c', '\u200f', '\u200e', '\u00a0'):
        text = text.replace(ch, '')
    text = text.replace('ي', 'ی').replace('ك', 'ک')
    text = ''.join(text.split())
    return text


def is_public_technical_key(key: str) -> bool:
    """آیا این کلید اطلاعات فنی/داخلی است و نباید در صفحه عمومی بیاید؟"""
    raw = str(key or '')
    kl = raw.lower()
    kn = _normalize_public_key(raw)
    for m in PUBLIC_TECHNICAL_KEY_MARKERS:
        if m in raw or m in kl:
            return True
        if _normalize_public_key(m) and _normalize_public_key(m) in kn:
            return True
    return False


def is_public_hero_dedup_key(key: str) -> bool:
    """کلیدهایی که در بخش‌های بالای صفحه نمایش داده شده‌اند."""
    raw = str(key or '')
    kl = raw.lower()
    kn = _normalize_public_key(raw)
    for m in PUBLIC_HERO_DEDUP_KEY_MARKERS:
        if m in raw or m in kl:
            return True
        if _normalize_public_key(m) and _normalize_public_key(m) in kn:
            return True
    return False


def filter_public_feature_highlights(feature_profile: dict, highlights: list) -> list:
    """برچسب‌های تکراری با feature_profile.core و متن‌های شبیه توضیحات را حذف می‌کند."""
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
        if is_public_technical_key(label) or is_public_technical_key(base):
            continue
        # هایلایت‌های شبیه توضیحات بلند / کلیدهای متنی
        low = label.lower()
        if any(m in label or m in low for m in ('توضیح', 'متن آگهی', 'description', 'شرح')):
            continue
        if len(label) > 80:
            continue
        filtered.append(label)
    return filtered


def scrub_public_feature_profile(feature_profile: Optional[dict]) -> dict:
    """حذف آیتم‌های متنی/توضیحات از گروه‌های امکانات صفحه عمومی."""
    if not feature_profile:
        return {}
    profile = dict(feature_profile)
    groups = []
    for group in profile.get('groups') or []:
        items = []
        for item in group.get('items') or []:
            key = str(item.get('key') or item.get('label') or '')
            val = str(item.get('value') or '')
            if is_public_technical_key(key):
                continue
            if any(
                (m in key.lower()) if m.isascii() else (m in key)
                for m in _DESC_KEY_MARKERS
            ):
                continue
            if len(val) > 180:
                continue
            items.append(item)
        if items:
            groups.append({**group, 'items': items})
    profile['groups'] = groups
    profile['detail_count'] = sum(len(g['items']) for g in groups) + sum(
        1 for c in (profile.get('core') or []) if c.get('known')
    )
    profile['has_details'] = bool(groups) or any(
        c.get('known') for c in (profile.get('core') or [])
    )
    return profile


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
        items.append({'label': 'قیمت', 'value': primary, 'kind': 'price', 'icon': 'fa-tags'})
        pps = _get(listing_like, 'price_per_sqm')
        if tx.get('show_price_per_sqm') and pps:
            items.append({'label': 'قیمت هر متر', 'value': format_toman(pps, per_sqm=True), 'kind': 'pps', 'icon': 'fa-chart-line'})

    if tx.get('show_deposit'):
        deposit = _get(listing_like, 'deposit')
        if deposit:
            dep_label = format_toman(deposit)
            items.append({'label': 'ودیعه', 'value': dep_label, 'kind': 'deposit', 'icon': 'fa-hand-holding-dollar'})
            if not primary:
                primary = f'ودیعه {dep_label}'
        elif data:
            from workspace.services.display import _listing_text_deposit
            txt = _listing_text_deposit(data)
            if txt:
                items.append({'label': 'ودیعه', 'value': txt, 'kind': 'deposit', 'icon': 'fa-hand-holding-dollar'})
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
                items.append({'label': 'اجاره ماهانه', 'value': 'بدون اجاره', 'kind': 'rent', 'icon': 'fa-calendar-day'})
                if not note and tx.get('show_deposit'):
                    note = 'رهن کامل'
            elif rent_num is not None and rent_num > 0:
                rent_label = format_toman(rent_num)
                items.append({'label': 'اجاره ماهانه', 'value': rent_label, 'kind': 'rent', 'icon': 'fa-calendar-day'})
                if not primary:
                    primary = f'اجاره {rent_label}'
            elif rent_num is None:
                from workspace.services.display import _listing_text_rent
                txt = _listing_text_rent(data)
                if txt:
                    items.append({'label': 'اجاره ماهانه', 'value': txt, 'kind': 'rent', 'icon': 'fa-calendar-day'})
        elif data:
            from workspace.services.display import _listing_text_rent
            txt = _listing_text_rent(data)
            if txt:
                items.append({'label': 'اجاره ماهانه', 'value': txt, 'kind': 'rent', 'icon': 'fa-calendar-day'})

    # اگر فقط ودیعه داریم و اجاره در داده نیست ولی معامله اجاره‌ای است
    if tx.get('show_rent') and not any(i['kind'] == 'rent' for i in items):
        deposit = _get(listing_like, 'deposit')
        rent = _get(listing_like, 'rent')
        if deposit and (rent in (None, 0, 0.0, '')):
            items.append({'label': 'اجاره ماهانه', 'value': 'بدون اجاره', 'kind': 'rent', 'icon': 'fa-calendar-day'})
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
    office = build_agency_office_block(ws)
    photo = ws.consultant_photo if ws.consultant_photo else None
    photo_url = _media_url_or_none(photo) or _media_url_or_none(ws.agency_logo)
    card_url = _media_url_or_none(ws.business_card_image)
    has_consultant_socials = bool(social_items)
    has_agency_socials = office['has_socials']
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
        'photo': photo or ws.agency_logo,
        'photo_url': photo_url,
        'has_photo': bool(photo_url),
        'business_card_url': card_url,
        'has_business_card': bool(card_url),
        'welcome_message': welcome['welcome_plain'] or welcome_html_to_plain(welcome['welcome_message']),
        'welcome_message_html': welcome['welcome_message_html'],
        'has_welcome': bool(welcome['welcome_message']),
        'social_links': socials,
        'social_networks': social_items,
        'has_socials': has_consultant_socials or has_agency_socials,
        'consultant_social_networks': social_items,
        'has_consultant_socials': has_consultant_socials,
        'agency_social_networks': office['social_networks'],
        'has_agency_socials': has_agency_socials,
        'agency': office,
        'has_agency_address': office['has_address'],
        'has_agency_landlines': office['has_landlines'],
        'has_agency_website': office['has_website'],
        'has_office_navigation': office['has_map_navigation'],
        'whatsapp_icon_file': WHATSAPP_ICON_FILE,
        'telegram_icon_file': _SOCIAL_BY_KEY['telegram']['icon_file'],
        'active_files_count': active_count,
        'is_verified': bool(ws.agency_name and (ws.agency_logo or ws.consultant_photo)),
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
            if also_hide_description and any(
                m in key.lower() if m.isascii() else m in key
                for m in ('توضیح', 'description', 'متن آگهی', 'شرح', 'amenities')
            ):
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


_DESC_SECTION_NAMES = frozenset({'توضیحات', 'متن', 'شرح'})
_DESC_KEY_MARKERS = (
    'توضیح', 'description', 'متن آگهی', 'شرح', 'توضیحات', 'amenities', 'امکانات و توضیحات',
)
_HERO_SECTION_NAMES = frozenset({'شرایط مالی', 'مالی', 'مشخصات اصلی', 'ملک'})


def _normalize_public_text(value: str) -> str:
    text = str(value or '').strip().lower()
    for ch in ('\u200c', '\u200f', '\u200e', ' ', '\n', '\r', '\t'):
        text = text.replace(ch, '')
    return text


def texts_are_equivalent(a: str, b: str) -> bool:
    """مقایسه تقریبی دو متن برای تشخیص تکرار در صفحه عمومی."""
    na, nb = _normalize_public_text(a), _normalize_public_text(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # یکی زیرمجموعهٔ دیگری با طول کافی
    shorter, longer = (na, nb) if len(na) <= len(nb) else (nb, na)
    return len(shorter) >= 40 and shorter in longer


def prune_public_detail_sections(
    sections: Dict[str, Dict[str, str]],
    section_rows: Dict[str, list],
    *,
    has_description: bool = False,
    description_text: str = '',
    hide_hero_sections: bool = True,
) -> tuple[Dict[str, Dict[str, str]], Dict[str, list]]:
    """
    حذف سکشن‌ها/فیلدهای تکراری با بلوک‌های بالای صفحه عمومی
    (توضیحات، مالی، مشخصات اصلی).
    """
    cleaned_sections: Dict[str, Dict[str, str]] = {}
    cleaned_rows: Dict[str, list] = {}
    desc = (description_text or '').strip()
    hide_desc = has_description or bool(desc)

    for name, fields in (sections or {}).items():
        if hide_desc and name in _DESC_SECTION_NAMES:
            continue
        if hide_hero_sections and name in _HERO_SECTION_NAMES:
            continue

        kept_fields: Dict[str, str] = {}
        for key, val in (fields or {}).items():
            key_s = str(key or '')
            key_l = key_s.lower()
            if hide_desc and any(
                (m in key_l) if m.isascii() else (m in key_s)
                for m in _DESC_KEY_MARKERS
            ):
                continue
            val_s = str(val or '')
            # مقادیر خیلی بلند یا همان متن توضیحات — در تب تکرار نشوند
            if hide_desc and len(val_s) > 180:
                continue
            if desc and texts_are_equivalent(desc, val_s):
                continue
            kept_fields[key] = val
        if not kept_fields:
            continue

        rows = section_rows.get(name) or []
        kept_keys = set(kept_fields.keys())
        kept_rows = [
            row for row in rows
            if str(row.get('raw_key') or '') in kept_keys
            or (
                not row.get('raw_key')
                and str(row.get('key') or '') in kept_keys
            )
        ]
        cleaned_sections[name] = kept_fields
        cleaned_rows[name] = kept_rows

    return cleaned_sections, cleaned_rows


def public_feature_details_flag(feature_profile: Optional[dict]) -> bool:
    """آیا تب/آکاردئون امکانات جزئیات اضافه دارد؟ (نه تکرار core بالای صفحه)."""
    if not feature_profile:
        return False
    groups = feature_profile.get('groups') or []
    return any((g.get('items') or []) for g in groups)
