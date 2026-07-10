"""ابزارهای مشترک اشتراک عمومی آگهی و فایل شخصی."""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote

from django.conf import settings
from django.urls import reverse

from workspace.mixins import get_or_create_settings
from workspace.models import WorkspaceSettings

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
    form_vals = share_consultant_form_values(share.created_by, share)
    return {
        'share_url': share_url,
        'share_token': share.share_token,
        'view_count': share.view_count,
        'is_active': share.is_active,
        'consultant_name': form_vals['consultant_name'],
        'consultant_phone': form_vals['consultant_phone'],
        'consultant_name_stored': share.consultant_name,
        'consultant_phone_stored': share.consultant_phone,
        'welcome_message': share.welcome_message,
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
        'welcome_message': share.welcome_message.strip(),
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
