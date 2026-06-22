"""
داده‌های نمایشی CRM — پوشش کامل سناریوها برای آموزش و تست.
فقط داده‌های کاربر مشخص‌شده (--username) ایجاد یا حذف می‌شود.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from workspace.constants import (
    ACTIVITY_TYPES,
    CRM_SOURCES,
    CRM_STATUSES,
    CRM_TYPES,
    DEAL_STAGES,
    DEFAULT_DEAL_CHECKLIST,
    LOST_REASONS,
    VISIT_OUTCOMES,
    VISIT_REJECT_REASONS,
)
from workspace.models import (
    CRMAgency,
    CRMAgencyMember,
    CRMAutomationRule,
    CRMDeal,
    CRMDealCommissionSplit,
    CRMMessageTemplate,
    CRMProperty,
    CRMSavedFilter,
    Customer,
    CustomerActivity,
    CustomerDocument,
    CustomerListing,
    PropertyContact,
    PropertyVisit,
    Reminder,
    WorkspaceSettings,
)
from workspace.services.crm_templates import ensure_default_templates

User = get_user_model()

TEHRAN_DISTRICTS = [
    ('تهران', 'منطقه ۱', 'جردن'),
    ('تهران', 'منطقه ۲', 'ولنجک'),
    ('تهران', 'منطقه ۳', 'پاسداران'),
    ('تهران', 'منطقه ۵', 'سعادت‌آباد'),
    ('تهران', 'منطقه ۶', 'یوسف‌آباد'),
    ('تهران', 'منطقه ۷', 'نارمک'),
    ('تهران', 'منطقه ۸', 'تهرانپارس'),
    ('کرج', 'کرج', 'گوهردشت'),
    ('تهران', 'منطقه ۴', 'پونک'),
    ('تهران', 'منطقه ۱', 'زعفرانیه'),
]

COORDS = [
    (35.7575, 51.4160), (35.8100, 51.4700), (35.7810, 51.4700),
    (35.7740, 51.3750), (35.7320, 51.4100), (35.7240, 51.4900),
    (35.7320, 51.5200), (35.8550, 50.9700), (35.7550, 51.3400),
    (35.8010, 51.4200),
]


def _checklist(done_ids=None):
    done = set(done_ids or [])
    return [
        {
            'id': item['id'],
            'label': item['label'],
            'required': bool(item.get('required', False)),
            'done': item['id'] in done,
        }
        for item in DEFAULT_DEAL_CHECKLIST
    ]


# ─── مخاطبین: همه انواع، وضعیت‌ها و منابع ───
CONTACTS = [
    {
        'name': 'علی رضایی',
        'phone': '09121234567',
        'phone_alt': '02188776655',
        'email': 'ali.rezaei@example.com',
        'job': 'مهندس نرم‌افزار',
        'customer_type': 'خریدار',
        'status': 'در حال پیگیری',
        'priority': 'بالا',
        'source': 'دیوار',
        'property_type': 'آپارتمان',
        'budget_min': 8_000_000_000,
        'budget_max': 12_000_000_000,
        'min_area': 90,
        'max_area': 130,
        'rooms': '۲',
        'areas': 'جردن، ولنجک، زعفرانیه',
        'tags': 'خریدار جدی,بازدید,نورگیر',
        'notes': 'دنبال آپارتمان نوساز با پارکینگ. بودجه قابل مذاکره است. همسرش فردا تماس می‌گیرد.',
        'follow_offset': 0,
    },
    {
        'name': 'مریم احمدی',
        'phone': '09129876543',
        'customer_type': 'فروشنده',
        'status': 'بازدید انجام شد',
        'priority': 'بالا',
        'source': 'معرف',
        'property_type': 'آپارتمان',
        'budget_min': 9_500_000_000,
        'budget_max': 10_500_000_000,
        'areas': 'پاسداران',
        'tags': 'فروش فوری,مالک مستقیم',
        'notes': 'ملک خودشه — عجله برای فروش داره. حداقل ۹.۸ می‌خواد.',
        'follow_offset': 1,
    },
    {
        'name': 'حسین کریمی',
        'phone': '09131112222',
        'customer_type': 'مالک',
        'status': 'قرارداد',
        'priority': 'بالا',
        'source': 'ورود به املاک',
        'property_type': 'ویلا',
        'deposit_min': 500_000_000,
        'deposit_max': 600_000_000,
        'rent_min': 25_000_000,
        'rent_max': 30_000_000,
        'areas': 'لواسان، باغستان',
        'tags': 'مالک,رهن و اجاره',
        'notes': 'ویلای دوبلکس — مستأجر فعلی تا ۳ ماه دیگه خالی می‌کنه.',
        'follow_offset': 5,
    },
    {
        'name': 'سارا موسوی',
        'phone': '09135556666',
        'customer_type': 'مستاجر',
        'status': 'جدید',
        'priority': 'بالا',
        'source': 'تماس ورودی',
        'property_type': 'آپارتمان',
        'deposit_min': 200_000_000,
        'deposit_max': 350_000_000,
        'rent_min': 15_000_000,
        'rent_max': 22_000_000,
        'min_area': 70,
        'max_area': 100,
        'rooms': '۲',
        'areas': 'سعادت‌آباد، یوسف‌آباد',
        'tags': 'مستاجر,فوری',
        'notes': 'زوج جوان — حیوان خانگی دارن، باید مجاز باشه.',
        'follow_offset': 0,
    },
    {
        'name': 'رضا نوری',
        'phone': '09137778888',
        'customer_type': 'موجر',
        'status': 'در حال پیگیری',
        'priority': 'متوسط',
        'source': 'اینستاگرام',
        'property_type': 'آپارتمان',
        'deposit_min': 300_000_000,
        'deposit_max': 400_000_000,
        'rent_min': 18_000_000,
        'rent_max': 22_000_000,
        'areas': 'نارمک',
        'tags': 'موجر',
        'follow_offset': -3,
    },
    {
        'name': 'فاطمه حسینی',
        'phone': '09139990000',
        'customer_type': 'سرمایه‌گذار',
        'status': 'در حال پیگیری',
        'priority': 'بالا',
        'source': 'سایت',
        'property_type': 'زمین',
        'budget_min': 20_000_000_000,
        'budget_max': 50_000_000_000,
        'areas': 'شمال شهر، لواسان',
        'tags': 'سرمایه‌گذار,زمین',
        'notes': 'دنبال زمین با مجوز ساخت — افق ۲ ساله.',
        'follow_offset': 4,
    },
    {
        'name': 'امیر سرنخی',
        'phone': '09121110001',
        'customer_type': 'سرنخ',
        'status': 'جدید',
        'priority': 'پایین',
        'source': 'دیوار',
        'property_type': 'آپارتمان',
        'areas': 'تهرانپارس',
        'notes': 'تماس اول — گفت فعلاً فقط قیمت‌ها رو می‌خواد بدونه.',
        'follow_offset': 1,
    },
    {
        'name': 'نگار صادقی',
        'phone': '09121110002',
        'customer_type': 'متقاضی خرید',
        'status': 'جدید',
        'priority': 'متوسط',
        'source': 'تلگرام',
        'property_type': 'آپارتمان',
        'budget_min': 5_000_000_000,
        'budget_max': 7_000_000_000,
        'areas': 'کرج، گوهردشت',
        'follow_offset': -1,
    },
    {
        'name': 'پریسا جعفری',
        'phone': '09121110003',
        'customer_type': 'متقاضی اجاره',
        'status': 'در حال پیگیری',
        'priority': 'متوسط',
        'source': 'دیوار',
        'property_type': 'آپارتمان',
        'deposit_min': 150_000_000,
        'deposit_max': 250_000_000,
        'rent_min': 12_000_000,
        'rent_max': 18_000_000,
        'areas': 'یوسف‌آباد، پونک',
        'follow_offset': 2,
    },
    {
        'name': 'محمد فروشنده‌ای',
        'phone': '09121110004',
        'customer_type': 'فروشنده ملک',
        'status': 'بازدید انجام شد',
        'priority': 'بالا',
        'source': 'معرف',
        'property_type': 'آپارتمان',
        'budget_min': 9_500_000_000,
        'budget_max': 10_000_000_000,
        'areas': 'جردن',
        'tags': 'فروشنده ملک,فایل شخصی',
        'follow_offset': 3,
    },
    {
        'name': 'شرکت ساختمانی آریا',
        'phone': '02188776655',
        'phone_alt': '09121110005',
        'email': 'sales@arya-build.ir',
        'customer_type': 'اشخاص حقوقی',
        'status': 'در حال پیگیری',
        'priority': 'بالا',
        'source': 'ورود به املاک',
        'is_legal_entity': True,
        'company_name': 'شرکت ساختمانی آریا',
        'national_id': '10123456789',
        'property_type': 'اداری',
        'budget_min': 30_000_000_000,
        'budget_max': 80_000_000_000,
        'areas': 'مرکز شهر، جردن',
        'tags': 'حقوقی,پروژه,B2B',
        'notes': 'دنبال واحد اداری ۲۰۰+ متر — پارکینگ اختصاصی الزامی.',
        'follow_offset': 6,
    },
    {
        'name': 'کامران تبدیل‌شده',
        'phone': '09121110006',
        'customer_type': 'خریدار',
        'status': 'در حال پیگیری',
        'priority': 'متوسط',
        'source': 'دیوار',
        'property_type': 'آپارتمان',
        'budget_min': 6_000_000_000,
        'budget_max': 8_000_000_000,
        'areas': 'ولنجک',
        'tags': 'تبدیل‌شده از سرنخ',
        'from_lead': True,
        'follow_offset': 0,
    },
    {
        'name': 'زهرا بایگانی',
        'phone': '09121110007',
        'customer_type': 'خریدار',
        'status': 'بایگانی',
        'priority': 'پایین',
        'source': 'سایر',
        'notes': 'انصراف داد — گفت ۶ ماه دیگه برمی‌گرده.',
        'follow_offset': None,
    },
    {
        'name': 'مهدی معوق',
        'phone': '09121110008',
        'customer_type': 'خریدار',
        'status': 'در حال پیگیری',
        'priority': 'بالا',
        'source': 'تماس ورودی',
        'property_type': 'آپارتمان',
        'budget_min': 4_000_000_000,
        'budget_max': 6_000_000_000,
        'areas': 'تهرانپارس',
        'tags': 'معوق,پیگیری فوری',
        'notes': '۳ روزه پیگیری نشده — اولویت تماس امروز.',
        'follow_offset': -4,
    },
    {
        'name': 'لیلا قراردادی',
        'phone': '09121110009',
        'customer_type': 'خریدار',
        'status': 'قرارداد',
        'priority': 'بالا',
        'source': 'معرف',
        'property_type': 'آپارتمان',
        'budget_min': 11_000_000_000,
        'budget_max': 12_500_000_000,
        'areas': 'جردن',
        'tags': 'قرارداد,خرید جدی',
        'follow_offset': 7,
    },
    {
        'name': 'آرش ستوده',
        'phone': '09121110010',
        'customer_type': 'خریدار',
        'status': 'در حال پیگیری',
        'priority': 'متوسط',
        'source': 'دیوار',
        'property_type': 'آپارتمان',
        'budget_min': 7_000_000_000,
        'budget_max': 9_000_000_000,
        'areas': 'پونک',
        'tags': 'غیرفعال,اتوماسیون',
        'notes': '۱۰ روز بدون تماس — تست قانون اتوماسیون.',
        'stagnant_days': 10,
        'follow_offset': -10,
    },
    {
        'name': 'بهنام کلنگی‌کار',
        'phone': '09121110011',
        'customer_type': 'خریدار',
        'status': 'بازدید انجام شد',
        'priority': 'بالا',
        'source': 'دیوار',
        'property_type': 'کلنگی',
        'budget_min': 15_000_000_000,
        'budget_max': 25_000_000_000,
        'areas': 'تهرانپارس، نارمک',
        'tags': 'کلنگی,ساخت‌وساز',
        'notes': 'سازنده هست — دنبال کلنگی با گذر عرض.',
        'follow_offset': 2,
    },
    {
        'name': 'سمانه نوروزی',
        'phone': '09121110012',
        'customer_type': 'خریدار',
        'status': 'در حال پیگیری',
        'priority': 'متوسط',
        'source': 'سایت',
        'property_type': 'آپارتمان',
        'budget_min': 3_500_000_000,
        'budget_max': 5_000_000_000,
        'areas': 'پونک، جنت‌آباد',
        'tags': 'پیش‌فروش',
        'notes': 'علاقه‌مند پروژه‌های در حال ساخت.',
        'follow_offset': 5,
    },
    {
        'name': 'دکتر رحیمی',
        'phone': '09121110013',
        'email': 'dr.rahimi@clinic.ir',
        'job': 'پزشک',
        'customer_type': 'خریدار',
        'status': 'جدید',
        'priority': 'بالا',
        'source': 'معرف',
        'property_type': 'اداری',
        'budget_min': 12_000_000_000,
        'budget_max': 18_000_000_000,
        'areas': 'جردن، ونک',
        'tags': 'اداری,مطب',
        'follow_offset': 0,
    },
    {
        'name': 'نرگس موج‌پور',
        'phone': '09121110014',
        'customer_type': 'موجر',
        'status': 'در حال پیگیری',
        'priority': 'پایین',
        'source': 'تماس ورودی',
        'property_type': 'آپارتمان',
        'deposit_min': 400_000_000,
        'deposit_max': 500_000_000,
        'rent_min': 20_000_000,
        'rent_max': 25_000_000,
        'areas': 'سعادت‌آباد',
        'follow_offset': 3,
    },
]

PROPERTIES = [
    {
        'title': 'آپارتمان ۱۲۰ متری جردن — نوساز طبقه ۴',
        'property_type': 'آپارتمان', 'deal_mode': 'فروش',
        'transaction_status': 'فعال', 'publish_status': 'منتشرشده',
        'area': 120, 'rooms': '۳', 'floor': 4, 'total_floors': 6,
        'has_parking': True, 'has_storage': True, 'has_elevator': True,
        'build_year': 1401, 'sale_price': 12_500_000_000,
        'district_idx': 0, 'token': 'demo-jordan-120', 'pipeline_order': 0,
        'notes': 'نورگیر عالی — مالک شخصی. بازدیدهای زیاد داشته.',
    },
    {
        'title': 'ویلای ۲۵۰ متری لواسان — رهن و اجاره',
        'property_type': 'ویلا', 'deal_mode': 'رهن و اجاره',
        'transaction_status': 'در مذاکره', 'publish_status': 'منتشرشده',
        'area': 250, 'rooms': '۴', 'floor': 2, 'total_floors': 2,
        'has_parking': True, 'has_storage': True, 'build_year': 1395,
        'deposit': 500_000_000, 'monthly_rent': 28_000_000,
        'district_idx': 1, 'token': 'demo-lavasan-villa', 'pipeline_order': 1,
    },
    {
        'title': 'آپارتمان ۸۵ متری پاسداران — فروش فوری',
        'property_type': 'آپارتمان', 'deal_mode': 'فروش',
        'transaction_status': 'قرارداد', 'publish_status': 'مخفی',
        'area': 85, 'rooms': '۲', 'floor': 3, 'total_floors': 5,
        'has_parking': True, 'has_elevator': True, 'build_year': 1398,
        'sale_price': 9_800_000_000,
        'district_idx': 2, 'token': 'demo-pasdaran-85', 'pipeline_order': 0,
    },
    {
        'title': 'آپارتمان ۹۵ متری سعادت‌آباد — اجاره',
        'property_type': 'آپارتمان', 'deal_mode': 'اجاره',
        'transaction_status': 'فعال', 'publish_status': 'منتشرشده',
        'area': 95, 'rooms': '۲', 'floor': 7, 'total_floors': 10,
        'has_parking': True, 'has_storage': True, 'has_elevator': True,
        'build_year': 1400, 'deposit': 300_000_000, 'monthly_rent': 20_000_000,
        'district_idx': 3, 'token': 'demo-saadat-95', 'pipeline_order': 2,
    },
    {
        'title': 'زمین ۵۰۰ متری شمال — مجوز ساخت',
        'property_type': 'زمین', 'deal_mode': 'فروش',
        'transaction_status': 'فعال', 'publish_status': 'پیش‌نویس',
        'area': 500, 'sale_price': 25_000_000_000,
        'district_idx': 1, 'token': 'demo-land-north', 'pipeline_order': 0,
    },
    {
        'title': 'واحد اداری ۱۵۰ متری ونک — فروخته شد',
        'property_type': 'اداری', 'deal_mode': 'فروش',
        'transaction_status': 'فروخته‌شده', 'publish_status': 'بایگانی',
        'area': 150, 'floor': 12, 'total_floors': 20,
        'has_parking': True, 'has_elevator': True, 'build_year': 1390,
        'sale_price': 18_000_000_000,
        'district_idx': 4, 'token': 'demo-office-150', 'pipeline_order': 0,
    },
    {
        'title': 'مغازه ۴۰ متری نارمک — اجاره‌رفته',
        'property_type': 'مغازه', 'deal_mode': 'رهن و اجاره',
        'transaction_status': 'اجاره‌رفته', 'publish_status': 'بایگانی',
        'area': 40, 'deposit': 800_000_000, 'monthly_rent': 35_000_000,
        'district_idx': 5, 'token': 'demo-shop-narmak', 'pipeline_order': 0,
    },
    {
        'title': 'کلنگی ۲۰۰ متری تهرانپارس — گذر ۱۲ متر',
        'property_type': 'کلنگی', 'deal_mode': 'فروش',
        'transaction_status': 'فعال', 'publish_status': 'منتشرشده',
        'area': 200, 'sale_price': 18_000_000_000,
        'district_idx': 6, 'token': 'demo-kolangi-thpars', 'pipeline_order': 1,
    },
    {
        'title': 'پروژه پیش‌فروش پونک — ۱۱۰ متر',
        'property_type': 'آپارتمان', 'deal_mode': 'پیش‌فروش',
        'transaction_status': 'در مذاکره', 'publish_status': 'منتشرشده',
        'area': 110, 'rooms': '۲', 'floor': 5, 'total_floors': 8,
        'has_parking': True, 'has_elevator': True, 'build_year': 1404,
        'sale_price': 9_200_000_000,
        'district_idx': 8, 'token': 'demo-prefab-poonak', 'pipeline_order': 2,
    },
    {
        'title': 'آپارتمان ۷۵ متری یوسف‌آباد — اجاره',
        'property_type': 'آپارتمان', 'deal_mode': 'اجاره',
        'transaction_status': 'فعال', 'publish_status': 'منتشرشده',
        'area': 75, 'rooms': '۲', 'floor': 2, 'total_floors': 4,
        'has_elevator': True, 'build_year': 1395,
        'deposit': 250_000_000, 'monthly_rent': 16_000_000,
        'district_idx': 4, 'token': 'demo-yousef-75', 'pipeline_order': 3,
    },
    {
        'title': 'ویلای ۳۰۰ متری کرج گوهردشت',
        'property_type': 'ویلا', 'deal_mode': 'فروش',
        'transaction_status': 'بایگانی', 'publish_status': 'بایگانی',
        'area': 300, 'rooms': '۵', 'sale_price': 14_000_000_000,
        'district_idx': 7, 'token': 'demo-karaj-villa', 'pipeline_order': 0,
    },
    {
        'title': 'آپارتمان ۱۳۰ متری زعفرانیه — لوکس',
        'property_type': 'آپارتمان', 'deal_mode': 'فروش',
        'transaction_status': 'فعال', 'publish_status': 'منتشرشده',
        'area': 130, 'rooms': '۳', 'floor': 8, 'total_floors': 12,
        'has_parking': True, 'has_storage': True, 'has_elevator': True,
        'build_year': 1402, 'sale_price': 28_000_000_000,
        'district_idx': 9, 'token': 'demo-zaferan-130', 'pipeline_order': 4,
    },
]


class Command(BaseCommand):
    help = 'ایجاد داده‌های نمایشی CRM حرفه‌ای — فقط برای کاربر مشخص‌شده'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='qashqaeii', help='نام کاربری')
        parser.add_argument(
            '--clear',
            action='store_true',
            help='حذف داده‌های CRM قبلی این کاربر قبل از ایجاد',
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'کاربر «{options["username"]}» یافت نشد.'))
            return

        self.stdout.write(self.style.SUCCESS(f'کاربر «{user.username}» — seed CRM حرفه‌ای...\n'))

        if options['clear']:
            self._clear_crm_data(user)
            self.stdout.write(self.style.WARNING('داده‌های CRM قبلی این کاربر حذف شد.\n'))

        with transaction.atomic():
            agency, member = self._setup_agency(user)
            settings = self._setup_workspace(user)
            customers = self._create_customers(user, agency, member)
            properties = self._create_properties(user, agency)
            self._link_contacts(customers, properties)
            deals = self._create_deals(user, agency, customers, properties, member)
            self._create_visits(user, customers, properties)
            self._create_reminders(user, customers)
            self._create_activities(customers, properties)
            self._create_listings(customers, properties)
            self._create_documents(user, customers, properties)
            self._create_saved_filters(user)
            self._create_templates_and_automation(user)

        self._print_summary(user)

    def _clear_crm_data(self, user):
        agency_ids = list(CRMAgency.objects.filter(owner=user).values_list('pk', flat=True))
        if agency_ids:
            CRMDealCommissionSplit.objects.filter(deal__user=user).delete()
        CRMDeal.objects.filter(user=user).delete()
        PropertyVisit.objects.filter(user=user).delete()
        Reminder.objects.filter(user=user).delete()
        CustomerDocument.objects.filter(user=user).delete()
        CRMAutomationRule.objects.filter(user=user).delete()
        CRMMessageTemplate.objects.filter(user=user).delete()
        CRMSavedFilter.objects.filter(user=user).delete()
        Customer.objects.filter(user=user).delete()
        CRMProperty.objects.filter(user=user).delete()
        if agency_ids:
            CRMAgencyMember.objects.filter(agency_id__in=agency_ids).delete()
            CRMAgency.objects.filter(pk__in=agency_ids).delete()

    def _setup_agency(self, user):
        slug = slugify(f'demo-{user.username}') or f'demo-{user.pk}'
        agency, _ = CRMAgency.objects.get_or_create(
            slug=slug,
            defaults={'name': 'آژانس املاک نگین', 'owner': user},
        )
        member, _ = CRMAgencyMember.objects.get_or_create(
            agency=agency, user=user,
            defaults={'role': 'owner', 'title': 'مدیر و مشاور ارشد', 'is_active': True},
        )
        return agency, member

    def _setup_workspace(self, user):
        settings, _ = WorkspaceSettings.objects.get_or_create(user=user)
        settings.agency_name = 'آژانس املاک نگین'
        settings.crm_deal_stages = list(DEAL_STAGES)
        settings.save(update_fields=['agency_name', 'crm_deal_stages', 'updated_at'])
        return settings

    def _create_customers(self, user, agency, member):
        today = timezone.now().date()
        created = []
        lead_for_convert = None

        for i, raw in enumerate(CONTACTS):
            data = dict(raw)
            city, district, _ = TEHRAN_DISTRICTS[i % len(TEHRAN_DISTRICTS)]
            follow_offset = data.pop('follow_offset', None)
            from_lead = data.pop('from_lead', False)
            stagnant_days = data.pop('stagnant_days', None)

            customer = Customer.objects.create(
                user=user,
                agency=agency,
                assigned_to=user,
                city=city,
                district=district,
                **data,
            )
            if follow_offset is not None:
                customer.next_follow_up = today + timedelta(days=follow_offset)
                customer.save(update_fields=['next_follow_up'])

            days_ago = stagnant_days or random.randint(1, 40)
            updated_hours = (stagnant_days * 24 + 12) if stagnant_days else random.randint(2, 96)
            Customer.objects.filter(pk=customer.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago + 5),
                updated_at=timezone.now() - timedelta(hours=updated_hours),
            )
            customer.refresh_from_db()

            if from_lead:
                if lead_for_convert is None:
                    lead_for_convert = Customer.objects.create(
                        user=user, agency=agency, assigned_to=user,
                        name='سرنخ قدیمی — کامران (بایگانی)',
                        phone='09120000000', customer_type='سرنخ',
                        status='بایگانی', source='دیوار',
                        city='تهران', district='منطقه ۳',
                        notes='سرنخ اولیه قبل از تبدیل.',
                    )
                customer.converted_from = lead_for_convert
                customer.save(update_fields=['converted_from'])
            elif customer.customer_type == 'سرنخ' and lead_for_convert is None:
                lead_for_convert = customer

            created.append(customer)
        return created

    def _create_properties(self, user, agency):
        props = []
        for i, raw in enumerate(PROPERTIES):
            data = dict(raw)
            district_idx = data.pop('district_idx', i % len(TEHRAN_DISTRICTS))
            city, district, neighborhood = TEHRAN_DISTRICTS[district_idx]
            lat, lng = COORDS[district_idx % len(COORDS)]

            prop = CRMProperty.objects.create(
                user=user,
                agency=agency,
                city=city,
                district=district,
                neighborhood=neighborhood,
                address=f'خیابان اصلی {neighborhood}، {district}، {city}',
                latitude=lat + random.uniform(-0.008, 0.008),
                longitude=lng + random.uniform(-0.008, 0.008),
                link=f'https://divar.ir/v/{data.get("token", f"demo-{i}")}',
                amenities='آسانسور، پارکینگ، انباری، لابی',
                images=[f'/static/images/demo-property-{i + 1}.jpg'],
                **data,
            )
            days_ago = random.randint(3, 55)
            CRMProperty.objects.filter(pk=prop.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago),
                updated_at=timezone.now() - timedelta(hours=random.randint(1, 120)),
            )
            prop.refresh_from_db()
            props.append(prop)
        return props

    def _link_contacts(self, customers, properties):
        links = [
            (0, 0, 'خریدار', 'خرید', 'بالا', True, 'خریدار اصلی — جدی'),
            (0, 11, 'پیشنهادی', 'خرید', 'متوسط', False, 'گزینه لوکس‌تر'),
            (1, 2, 'فروشنده', 'فروش', 'بالا', True, 'مالک مستقیم'),
            (2, 1, 'مالک', 'رهن و اجاره', 'بالا', True, ''),
            (3, 3, 'مستاجر', 'اجاره', 'بالا', True, ''),
            (3, 9, 'پیشنهادی', 'اجاره', 'متوسط', False, 'گزینه دوم'),
            (4, 3, 'موجر', 'رهن و اجاره', 'بالا', True, ''),
            (5, 4, 'سرمایه‌گذار', 'سرمایه‌گذاری', 'بالا', False, ''),
            (9, 0, 'فروشنده', 'فروش', 'بالا', True, ''),
            (10, 5, 'خریدار', 'خرید', 'بالا', True, 'شرکت حقوقی'),
            (11, 0, 'خریدار', 'خرید', 'بالا', True, ''),
            (14, 0, 'خریدار', 'خرید', 'بالا', True, 'در حال قرارداد'),
            (16, 7, 'خریدار', 'خرید', 'بالا', True, 'کلنگی'),
            (17, 8, 'خریدار', 'پیش‌فروش', 'متوسط', True, ''),
            (18, 5, 'خریدار', 'خرید', 'بالا', True, 'مطب'),
            (19, 3, 'موجر', 'رهن و اجاره', 'متوسط', True, ''),
            (6, 0, 'سرنخ', 'خرید', 'پایین', False, 'هنوز جدی نیست'),
            (8, 9, 'متقاضی اجاره', 'اجاره', 'بالا', True, ''),
        ]
        for ci, pi, role, deal_type, interest, is_primary, notes in links:
            PropertyContact.objects.get_or_create(
                customer=customers[ci],
                property=properties[pi],
                role=role,
                defaults={
                    'deal_type': deal_type,
                    'interest_level': interest,
                    'is_primary': is_primary,
                    'notes': notes or 'ارتباط نمایشی آموزشی',
                },
            )

    def _create_deals(self, user, agency, customers, properties, member):
        today = timezone.now().date()
        deals_spec = [
            ('خرید آپارتمان جردن — سرنخ', 0, 0, 'سرنخ', 12_500_000_000, 25, 14, []),
            ('رهن ویلای لواسان — مذاکره', 2, 1, 'مذاکره', 500_000_000, 55, 21, ['deed']),
            ('فروش پاسداران — بازدید', 1, 2, 'بازدید', 9_800_000_000, 65, 10, ['deed', 'inquiry']),
            ('اجاره سعادت‌آباد — پیش‌قرارداد', 3, 3, 'پیش‌قرارداد', 300_000_000, 80, 7,
             ['deed', 'inquiry', 'owner_id', 'draft']),
            ('خرید جردن — قرارداد نهایی', 14, 0, 'قرارداد', 12_000_000_000, 95, 3,
             ['deed', 'inquiry', 'owner_id', 'buyer_id', 'deposit', 'draft']),
            ('فروش اداری ونک — موفق', 10, 5, 'بسته‌شده', 18_000_000_000, 100, -8,
             ['deed', 'inquiry', 'owner_id', 'buyer_id', 'deposit', 'draft']),
            ('خرید جردن — از دست رفته (قیمت)', 8, 0, 'از دست رفته', 12_500_000_000, 0, -12, [], LOST_REASONS[0]),
            ('پونک — از دست رفته (رقبا)', 7, 8, 'از دست رفته', 9_200_000_000, 0, -6, [], LOST_REASONS[1]),
            ('ولنجک — انصراف مشتری', 11, 0, 'از دست رفته', 7_500_000_000, 0, -4, [], LOST_REASONS[2]),
            ('پاسداران — ملک فروخته شد', 12, 2, 'از دست رفته', 9_800_000_000, 0, -2, [], LOST_REASONS[3]),
            ('کلنگی — مدارک ناقص', 16, 7, 'از دست رفته', 18_000_000_000, 0, -15, [], LOST_REASONS[4]),
            ('زعفرانیه — سایر', 18, 11, 'از دست رفته', 28_000_000_000, 0, -9, [], LOST_REASONS[5]),
        ]
        created_deals = []
        for row in deals_spec:
            lost_reason = row[8] if len(row) > 8 else ''
            title, ci, pi, stage, value, prob, close_offset, done_ids = row[:8]
            close_date = today + timedelta(days=close_offset)
            deal = CRMDeal.objects.create(
                user=user,
                agency=agency,
                assigned_to=user,
                customer=customers[ci],
                property=properties[pi],
                listing_token=properties[pi].token,
                title=title,
                stage=stage,
                checklist=_checklist(done_ids),
                value=value,
                probability=prob,
                expected_close_date=close_date,
                commission_rate=1.25,
                commission_amount=int(value * 0.0125) if value and stage == 'بسته‌شده' else None,
                notes=self._deal_note(stage, customers[ci].name),
            )
            if stage == 'بسته‌شده':
                deal.contract_number = 'NGN-1404-0042'
                deal.contract_amount = value
                deal.contract_date = today - timedelta(days=8)
                deal.closed_at = timezone.now() - timedelta(days=8)
                deal.commission_amount = int(value * 0.0125)
                deal.save()
                if member:
                    CRMDealCommissionSplit.objects.get_or_create(
                        deal=deal, member=member,
                        defaults={'percent': 100.0, 'amount': deal.commission_amount},
                    )
            elif stage == 'از دست رفته':
                deal.lost_reason = lost_reason
                deal.closed_at = timezone.now() - timedelta(days=abs(close_offset) or 1)
                deal.probability = 0
                deal.save()
            created_deals.append(deal)
        return created_deals

    def _deal_note(self, stage, customer_name):
        notes = {
            'سرنخ': f'تماس اول با {customer_name} — نیاز به بازدید.',
            'مذاکره': 'مالک روی رهن سخت‌گیره — پیشنهاد میانه دادیم.',
            'بازدید': 'بازدید انجام شد — منتظر نظر نهایی.',
            'پیش‌قرارداد': 'بیعانه ۵۰ میلیون توافق شد — مدارک در حال جمع‌آوری.',
            'قرارداد': 'قرارداد در دفترخانه — هفته آینده.',
            'بسته‌شده': 'معامله با موفقیت بسته شد — کمیسیون دریافت شد.',
            'از دست رفته': 'پیگیری شد ولی فرصت از دست رفت.',
        }
        return notes.get(stage, 'معامله نمایشی آموزشی')

    def _create_visits(self, user, customers, properties):
        today = timezone.now().date()
        visits = [
            (0, 0, 0, 'پسندید', '', 'ملک رو پسندید — منتظر نظر همسر.'),
            (1, 2, -2, 'رد', 'قیمت', 'گفت ۹.۸ زیاده — ۹.۲ می‌ده max.'),
            (3, 3, 0, 'در انتظار', '', 'بازدید امروز — هنوز نتیجه نداده.'),
            (14, 0, -1, 'پسندید', '', 'آماده پیش‌قرارداد.'),
            (8, 0, -7, 'رد', 'موقعیت', 'محله رو نپسندید.'),
            (5, 4, 5, 'در انتظار', '', 'بازدید زمین هفته بعد.'),
            (16, 7, 1, 'بازدید مجدد', '', 'با پیمانکار میاد دوباره.'),
            (11, 8, -3, 'رد', 'متراژ', '۱۱۰ متر کمه — ۱۳۰ می‌خواد.'),
            (17, 8, 2, 'در انتظار', '', 'پروژه رو دید — فکر می‌کنه.'),
            (6, 0, 3, 'رد', 'نور و تهویه', 'طبقه ۴ رو کم نور دید.'),
            (0, 9, -1, 'رد', 'طبقه', 'طبقه ۲ می‌خواد.'),
            (18, 5, -5, 'پسندید', '', 'اداری مناسب مطب.'),
        ]
        for ci, pi, day_offset, outcome, reject, note in visits:
            PropertyVisit.objects.create(
                user=user,
                customer=customers[ci],
                property=properties[pi],
                listing_token=properties[pi].token,
                listing_title=properties[pi].title,
                visit_date=today + timedelta(days=day_offset),
                outcome=outcome,
                reject_reason=reject,
                notes=note,
            )

    def _create_reminders(self, user, customers):
        now = timezone.now()
        today = now.date()
        reminders = [
            ('تماس فوری — مهدی معوق', 13, -4, False, ''),
            ('پیگیری سارا موسوی', 3, 0, False, ''),
            ('یادآوری بازدید جردن', 0, 1, False, ''),
            ('ارسال لیست به علی', 0, 0, False, ''),
            ('پیگیری هفتگی رضا نوری', 4, 7, False, 'weekly'),
            ('پیگیری دو هفته‌ای سرمایه‌گذار', 5, 14, False, 'biweekly'),
            ('پیگیری ماهانه موجر', 19, 30, False, 'monthly'),
            ('تماس انجام‌شده — بایگانی', 12, -5, True, ''),
            ('یادآور امروز عصر — لیلا', 14, 0, False, ''),
            ('پیگیری کلنگی بهنام', 16, 2, False, ''),
            ('تماس سرنخ امیر', 6, 1, False, ''),
        ]
        for title, ci, day_offset, is_done, recurrence in reminders:
            if day_offset == 0 and 'عصر' in title:
                due = now.replace(hour=17, minute=30, second=0, microsecond=0)
            elif day_offset == 0 and 'لیست' in title:
                due = now.replace(hour=11, minute=0, second=0, microsecond=0)
            elif day_offset == 0:
                due = now.replace(hour=9, minute=30, second=0, microsecond=0)
            else:
                due = timezone.make_aware(
                    datetime.combine(
                        today + timedelta(days=day_offset),
                        datetime.min.time().replace(hour=9, minute=0),
                    )
                )
            Reminder.objects.create(
                user=user,
                customer=customers[ci],
                title=title,
                note=f'یادآور آموزشی — {customers[ci].name}',
                due_at=due,
                is_done=is_done,
                recurrence=recurrence,
            )

    def _create_activities(self, customers, properties):
        activity_samples = [
            ('تماس', 'تماس ورودی — درخواست بازدید هفته آینده.', 12),
            ('واتساپ', 'ارسال ۳ ملک مناسب + لینک دیوار.', 8),
            ('پیامک', 'یادآوری بازدید فردا ساعت ۱۰.', 5),
            ('بازدید', 'بازدید حضوری — ۴۵ دقیقه.', 30),
            ('جلسه', 'جلسه در دفتر آژانس — مذاکره قیمت.', 60),
            ('یادداشت', 'مشتری طبقات ۳ تا ۷ را ترجیح می‌دهد.', None),
            ('پیگیری', 'پیگیری تلفنی — هنوز تصمیم نگرفته.', 10),
            ('تغییر وضعیت', 'وضعیت از «جدید» به «در حال پیگیری» تغییر کرد.', None),
            ('ایمیل', 'ارسال بروشور PDF ملک.', None),
            ('املاک', 'ملک جدید به پرونده اضافه شد.', None),
            ('وظیفه', 'هماهنگی با دفترخانه برای قرارداد.', None),
            ('یادآور', 'یادآور پیگیری هفتگی ثبت شد.', None),
        ]
        valid = [s for s in activity_samples if s[0] in ACTIVITY_TYPES]
        for i, customer in enumerate(customers):
            count = 5 if customer.status == 'بایگانی' else 6
            for j, (atype, content, duration) in enumerate(valid[:count]):
                prop = properties[(i + j) % len(properties)] if j % 2 == 0 else None
                act = CustomerActivity.objects.create(
                    customer=customer,
                    activity_type=atype,
                    title=atype,
                    content=content,
                    property=prop,
                    duration_minutes=duration,
                )
                days_ago = (i * 2) + j + 1
                CustomerActivity.objects.filter(pk=act.pk).update(
                    created_at=timezone.now() - timedelta(days=days_ago),
                )

    def _create_listings(self, customers, properties):
        listings = [
            (0, 0, 'Aaw3b9X1', 'آپارتمان ۱۱۵ متری جردن — ۱۲.۵ میلیارد', '۱۲,۵۰۰,۰۰۰,۰۰۰', '۱۱۵'),
            (0, 11, 'Bbx7k2M9', 'آپارتمان ۱۳۰ متری زعفرانیه — ۲۸ میلیارد', '۲۸,۰۰۰,۰۰۰,۰۰۰', '۱۳۰'),
            (3, 3, 'Ccy4p8N2', 'اجاره ۹۵ متری سعادت‌آباد', '۳۰۰,۰۰۰,۰۰۰ / ۲۰ م', '۹۵'),
            (3, 9, 'Ddz1q5R7', 'اجاره ۷۵ متری یوسف‌آباد', '۲۵۰,۰۰۰,۰۰۰ / ۱۶ م', '۷۵'),
            (5, 4, 'Eew9s3T4', 'زمین ۵۰۰ متری شمال', '۲۵,۰۰۰,۰۰۰,۰۰۰', '۵۰۰'),
            (8, 9, 'Ffx2u6V8', 'پیش‌فروش ۱۱۰ متری پونک', '۹,۲۰۰,۰۰۰,۰۰۰', '۱۱۰'),
            (16, 7, 'Ggy5w1X3', 'کلنگی ۲۰۰ متری تهرانپارس', '۱۸,۰۰۰,۰۰۰,۰۰۰', '۲۰۰'),
        ]
        for ci, pi, token, title, price, area in listings:
            CustomerListing.objects.create(
                customer=customers[ci],
                crm_property=properties[pi],
                token=token,
                title=title,
                price=price,
                area=area,
                link=f'https://divar.ir/v/{token}',
                role='پیشنهادی' if ci in (0, 3, 8) else 'خریدار',
                deal_type='خرید' if properties[pi].deal_mode == 'فروش' else 'اجاره',
                notes='آگهی دیوار مرتبط — داده آموزشی',
            )

    def _create_documents(self, user, customers, properties):
        docs = [
            ('کارت ملی علی رضایی', customers[0], None, 'کارت ملی'),
            ('شناسنامه — علی رضایی', customers[0], None, 'شناسنامه'),
            ('سند ملک پاسداران', customers[1], properties[2], 'سند'),
            ('استعلام پاسداران', customers[1], properties[2], 'استعلام'),
            ('قرارداد اجاره سعادت‌آباد', customers[3], properties[3], 'قرارداد'),
            ('پیش‌نویس قرارداد جردن', customers[14], properties[0], 'پیش‌نویس قرارداد'),
            ('مدارک شرکت آریا', customers[10], None, 'مدارک حقوقی'),
            ('تصاویر کلنگی تهرانپارس', customers[16], properties[7], 'تصاویر'),
        ]
        for title, customer, prop, doc_type in docs:
            content = ContentFile(
                f'[فایل آموزشی CRM]\n{title}\nمخاطب: {customer.name}\n'.encode('utf-8'),
                name=f'demo_{customer.pk}_{slugify(doc_type) or "doc"}.txt',
            )
            CustomerDocument.objects.create(
                user=user,
                customer=customer,
                property=prop,
                title=title,
                file=content,
                doc_type=doc_type,
            )

    def _create_saved_filters(self, user):
        filters = [
            ('خریداران جدی تهران', 'contacts',
             {'customer_type': 'خریدار', 'priority': 'بالا', 'status': 'در حال پیگیری'}, True),
            ('پیگیری‌های معوق', 'contacts', {'due': 'overdue'}, True),
            ('ملک‌های فعال فروش', 'properties',
             {'deal_mode': 'فروش', 'transaction_status': 'فعال'}, False),
            ('املاک در مذاکره', 'properties', {'transaction_status': 'در مذاکره'}, False),
            ('معاملات باز', 'deals', {'bucket': 'open'}, True),
            ('معاملات بسته‌شده', 'deals', {'stage': 'بسته‌شده'}, False),
            ('از دست رفته‌ها', 'deals', {'stage': 'از دست رفته'}, False),
        ]
        for name, scope, params, pinned in filters:
            CRMSavedFilter.objects.get_or_create(
                user=user, scope=scope, name=name,
                defaults={'params': params, 'is_pinned': pinned},
            )

    def _create_templates_and_automation(self, user):
        ensure_default_templates(user)
        extras = [
            ('پیامک یادآوری بازدید', 'بازدید', 'پیامک',
             '{name} عزیز، یادآوری بازدید امروز. {agency}'),
            ('پیشنهاد ملک واتساپ', 'پیشنهاد', 'واتساپ',
             'سلام {name}\nچند گزینه در {areas} آماده کردم. تماس بگیرید.\n{agency}'),
            ('پیگیری سرنخ', 'خوش‌آمد', 'واتساپ',
             'سلام {name}، ممنون از تماس. پرونده‌تون ثبت شد.'),
            ('قیمت‌گذاری مالک', 'سفارشی', 'واتساپ',
             'سلام\nبر اساس بازار محله، رنج قیمت پیشنهادی ما ...'),
        ]
        for name, category, channel, body in extras:
            CRMMessageTemplate.objects.get_or_create(
                user=user, name=name,
                defaults={'category': category, 'channel': channel, 'body': body, 'is_system': False},
            )
        rules = [
            ('پیگیری مخاطبین غیرفعال ۷ روزه', True, 7, 'جدید,در حال پیگیری',
             'create_reminder', 'پیگیری خودکار — بدون فعالیت', 1, '', ''),
            ('تغییر وضعیت سرنخ قدیمی (غیرفعال)', False, 30, 'جدید',
             'set_status', '', 0, 'بایگانی', ''),
            ('یادآور پیگیری ۳ روزه', True, 3, 'در حال پیگیری',
             'create_reminder', 'پیگیری سریع — ۳ روز سکوت', 0, '', ''),
        ]
        for name, active, days, statuses, action, rem_title, rem_days, act_status, _ in rules:
            CRMAutomationRule.objects.get_or_create(
                user=user, name=name,
                defaults={
                    'is_active': active,
                    'trigger': 'inactive_days',
                    'trigger_days': days,
                    'trigger_statuses': statuses,
                    'action': action,
                    'action_reminder_title': rem_title,
                    'action_reminder_days': rem_days,
                    'action_status': act_status,
                },
            )

    def _print_summary(self, user):
        counts = {
            'مخاطبین': Customer.objects.filter(user=user).count(),
            'املاک': CRMProperty.objects.filter(user=user).count(),
            'ارتباط مخاطب-ملک': PropertyContact.objects.filter(customer__user=user).count(),
            'معاملات': CRMDeal.objects.filter(user=user).count(),
            'بازدیدها': PropertyVisit.objects.filter(user=user).count(),
            'یادآورها': Reminder.objects.filter(user=user).count(),
            'فعالیت‌ها': CustomerActivity.objects.filter(customer__user=user).count(),
            'آگهی‌های دیوار': CustomerListing.objects.filter(customer__user=user).count(),
            'مدارک': CustomerDocument.objects.filter(user=user).count(),
            'فیلترهای ذخیره': CRMSavedFilter.objects.filter(user=user).count(),
            'قالب پیام': CRMMessageTemplate.objects.filter(user=user).count(),
            'اتوماسیون': CRMAutomationRule.objects.filter(user=user).count(),
            'آژانس': CRMAgency.objects.filter(owner=user).count(),
        }
        stages = list(
            CRMDeal.objects.filter(user=user).values_list('stage', flat=True).distinct()
        )
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 52))
        self.stdout.write(self.style.SUCCESS('  داده‌های CRM آموزشی با موفقیت ایجاد شد'))
        self.stdout.write(self.style.SUCCESS('=' * 52))
        for label, count in counts.items():
            self.stdout.write(f'  {label}: {count}')
        self.stdout.write(f'\n  مراحل معامله: {", ".join(stages)}')
        self.stdout.write('\n  صفحات آموزشی:')
        pages = [
            '/workspace/crm/', '/workspace/crm/today/',
            '/workspace/crm/contacts/', '/workspace/crm/deals/',
            '/workspace/crm/properties/', '/workspace/crm/reminders/',
            '/workspace/crm/calendar/', '/workspace/crm/templates/',
            '/workspace/crm/automation/',
        ]
        for p in pages:
            self.stdout.write(f'    {p}')
        self.stdout.write('')
