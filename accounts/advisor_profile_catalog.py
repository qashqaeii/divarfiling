"""گزینه‌های استاندارد پروفایل حرفه‌ای مشاور."""
from __future__ import annotations

from typing import Dict, List, Tuple

JOB_ROLE_INDEPENDENT = 'independent'
JOB_ROLE_AGENCY_ADVISOR = 'agency_advisor'
JOB_ROLE_AGENCY_MANAGER = 'agency_manager'
JOB_ROLE_TEAM_LEAD = 'team_lead'

JOB_ROLES_REQUIRE_AGENCY: frozenset = frozenset({
    JOB_ROLE_AGENCY_ADVISOR,
    JOB_ROLE_AGENCY_MANAGER,
    JOB_ROLE_TEAM_LEAD,
})

JOB_ROLE_CHOICES: Tuple[Tuple[str, str], ...] = (
    (JOB_ROLE_INDEPENDENT, 'مشاور مستقل'),
    (JOB_ROLE_AGENCY_ADVISOR, 'مشاور آژانس'),
    (JOB_ROLE_AGENCY_MANAGER, 'مدیر آژانس'),
    (JOB_ROLE_TEAM_LEAD, 'سرپرست تیم'),
)

EXPERTISE_AREA_CHOICES: Tuple[Tuple[str, str], ...] = (
    ('sale', 'خرید و فروش'),
    ('rent', 'رهن و اجاره'),
    ('presale', 'پیش‌فروش'),
    ('partnership', 'مشارکت در ساخت'),
)

PROPERTY_SPECIALTY_CHOICES: Tuple[Tuple[str, str], ...] = (
    ('apartment', 'آپارتمان'),
    ('villa', 'ویلا'),
    ('land', 'زمین'),
    ('old_building', 'کلنگی'),
    ('commercial', 'تجاری'),
    ('office', 'اداری'),
    ('estate', 'مستغلات'),
)

IRAN_PROVINCE_CHOICES: Tuple[Tuple[str, str], ...] = (
    ('tehran', 'تهران'),
    ('alborz', 'البرز'),
    ('isfahan', 'اصفهان'),
    ('fars', 'فارس'),
    ('khorasan_razavi', 'خراسان رضوی'),
    ('east_azerbaijan', 'آذربایجان شرقی'),
    ('west_azerbaijan', 'آذربایجان غربی'),
    ('khuzestan', 'خوزستان'),
    ('mazandaran', 'مازندران'),
    ('gilan', 'گیلان'),
    ('kerman', 'کرمان'),
    ('yazd', 'یزد'),
    ('qom', 'قم'),
    ('other', 'سایر استان‌ها'),
)

EXPERTISE_LABELS: Dict[str, str] = dict(EXPERTISE_AREA_CHOICES)
PROPERTY_LABELS: Dict[str, str] = dict(PROPERTY_SPECIALTY_CHOICES)
JOB_ROLE_LABELS: Dict[str, str] = dict(JOB_ROLE_CHOICES)
PROVINCE_LABELS: Dict[str, str] = dict(IRAN_PROVINCE_CHOICES)

ALLOWED_EXPERTISE = frozenset(EXPERTISE_LABELS)
ALLOWED_PROPERTY = frozenset(PROPERTY_LABELS)
ALLOWED_JOB_ROLES = frozenset(JOB_ROLE_LABELS)

PROFILE_REWARD_FIELD_KEYS: Tuple[Tuple[str, str], ...] = (
    ('activity_scope', 'محدوده فعالیت'),
    ('years_experience', 'سابقه فعالیت'),
    ('expertise_areas', 'حوزه تخصص'),
    ('property_specialties', 'نوع ملک'),
    ('job_role', 'نقش شغلی'),
    ('agency_office', 'مشخصات آژانس'),
)
