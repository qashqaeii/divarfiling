"""متن اعلان‌های push — لحن محاوره‌ای برای مشاور املاک."""
from __future__ import annotations


def welcome_message() -> tuple[str, str]:
    return (
        'خوش اومدی!',
        'اعلان‌ها روشن شد. از این به بعد یادآور تماس، استخراج و کارهای امروزت رو بهت خبر می‌دم.',
    )


def reminder_call(contact_name: str, reminder_title: str, note: str) -> tuple[str, str]:
    title = 'وقت تماسه'
    name = (contact_name or '').strip()
    detail = (reminder_title or note or '').strip()
    if name and detail:
        body = f'با «{name}» تماس بگیر — {detail}'
    elif name:
        body = f'با «{name}» تماس بگیر، وقتشه.'
    elif detail:
        body = detail
    else:
        body = 'یادآورت برای تماس رسیده.'
    return title, body


def reminder_visit(contact_name: str, reminder_title: str, note: str) -> tuple[str, str]:
    title = 'وقت بازدیده'
    name = (contact_name or '').strip()
    detail = (reminder_title or note or '').strip()
    if name and detail:
        body = f'بازدید «{name}» — {detail}'
    elif name:
        body = f'بازدید با «{name}» الان سررسیده.'
    elif detail:
        body = detail
    else:
        body = 'یادآورت برای بازدید رسیده.'
    return title, body


def today_digest(total: int, overdue: int) -> tuple[str, str]:
    title = 'برنامه امروزت'
    if overdue > 0:
        body = (
            f'امروز {total} کار داری که {overdue} تاش عقب افتاده. '
            'یه سر بزن جمعش کن.'
        )
    else:
        body = f'امروز {total} کار توی صفته. یه نگاه بهش بنداز.'
    return title, body


def overdue_followup(overdue: int) -> tuple[str, str]:
    return (
        'چند تا پیگیری مونده',
        f'{overdue} مشتری منتظر پیگیریه. زودتر سراغشون برو.',
    )


def extract_complete(dataset_name: str, count: int) -> tuple[str, str]:
    return (
        'استخراج تموم شد',
        f'فایل «{dataset_name}» آماده‌ست — {count} آگهی توش ذخیره شد.',
    )


def extract_schedule_due(schedule_title: str) -> tuple[str, str]:
    return (
        'وقت استخراجه',
        f'«{schedule_title}» الان آماده اجراست. بزن بریم!',
    )


def new_dataset(dataset_name: str, count: int) -> tuple[str, str]:
    return (
        'فایل جدید اومد',
        f'«{dataset_name}» ساخته شد — {count} آگهی داخلشه.',
    )


def customer_match(contact_name: str, listing_title: str) -> tuple[str, str]:
    name = (contact_name or 'مشتری').strip()
    listing = (listing_title or 'یک آگهی').strip()
    return (
        'فایل مناسب پیدا شد',
        f'برای «{name}» آگهی «{listing}» خوب می‌خوره. یه نگاه بنداز.',
    )


def price_drop(listing_title: str, old_price: str, new_price: str) -> tuple[str, str]:
    listing = (listing_title or 'آگهی').strip()
    return (
        'قیمت پایین اومد',
        f'«{listing}» از {old_price} رسیده به {new_price}. شاید بد نباشه پیگیریش کنی.',
    )


def license_expiry(threshold: int, plan_label: str) -> tuple[str, str]:
    plan = (plan_label or 'پلن').strip()
    if threshold == 0:
        return (
            'لایسنس تموم شد',
            'برای ادامه کار با CRM و استخراج، لایسنس رو تمدید کن.',
        )
    if threshold == 1:
        return (
            'فردا لایسنس تموم میشه',
            f'پلن «{plan}» فقط تا فردا فعاله. وقتشه تمدید کنی.',
        )
    if threshold == 3:
        return (
            '۳ روز تا پایان لایسنس',
            f'پلن «{plan}» تا ۳ روز دیگه تموم میشه. زودتر فکرشو بکن.',
        )
    if threshold == 7:
        return (
            'یک هفته تا پایان لایسنس',
            f'پلن «{plan}» تا یک هفته دیگه تموم میشه.',
        )
    # 14 days
    return (
        'دو هفته تا پایان لایسنس',
        f'پلن «{plan}» تا دو هفته دیگه تموم میشه. وقتشه فکر تمدید کنی.',
    )


def test_push_message() -> tuple[str, str]:
    return (
        'تست اعلان',
        'اگه اینو میبینی بدون دوستت دارم',
    )
