"""
داده‌های نمایشی CRM برای تست تمام قابلیت‌ها.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workspace.constants import (
    ACTIVITY_TYPES,
    CRM_PRIORITIES,
    CRM_SOURCES,
    CRM_STATUSES,
    CRM_TYPES,
    DEAL_STAGES,
    DEAL_TYPES,
    INTEREST_LEVELS,
    LISTING_ROLES,
    LOST_REASONS,
    PROPERTY_DEAL_MODES,
    PROPERTY_PUBLISH_STATUSES,
    PROPERTY_TX_STATUSES,
    VISIT_OUTCOMES,
    VISIT_REJECT_REASONS,
)
from workspace.models import (
    CRMAutomationRule,
    CRMDeal,
    CRMMessageTemplate,
    CRMProperty,
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
]

CONTACTS = [
  {
    'name': 'علی رضایی',
    'phone': '09121234567',
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
    'areas': 'جردن، ولنجک',
    'tags': 'خریدار جدی,بازدید',
    'notes': 'به دنبال آپارتمان نوساز در شمال تهران.',
    'follow_offset': 0,
  },
  {
    'name': 'مریم احمدی',
    'phone': '09129876543',
    'customer_type': 'فروشنده',
    'status': 'بازدید انجام شد',
    'priority': 'متوسط',
    'source': 'معرف',
    'property_type': 'آپارتمان',
    'budget_min': 15_000_000_000,
    'budget_max': 16_500_000_000,
    'areas': 'پاسداران',
    'tags': 'فروش فوری',
    'notes': 'ملک شخصی — آماده مذاکره.',
    'follow_offset': 2,
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
    'areas': 'لواسان',
    'tags': 'مالک,رهن و اجاره',
    'notes': 'ویلای دوبلکس با حیاط.',
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
    'tags': 'مستاجر',
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
    'follow_offset': -2,
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
    'areas': 'شمال شهر',
    'tags': 'سرمایه‌گذار',
    'follow_offset': 3,
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
    'notes': 'تماس اولیه — هنوز نیاز دقیق مشخص نیست.',
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
    'areas': 'کرج',
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
    'areas': 'یوسف‌آباد',
    'follow_offset': 4,
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
    'follow_offset': 7,
  },
  {
    'name': 'شرکت ساختمانی آریا',
    'phone': '02188776655',
    'phone_alt': '09121110005',
    'email': 'info@arya-build.ir',
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
    'areas': 'مرکز شهر',
    'tags': 'حقوقی,پروژه',
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
    'notes': 'انصراف داد — بایگانی شده.',
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
    'tags': 'معوق',
    'follow_offset': -5,
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
    'budget_max': 12_000_000_000,
    'areas': 'جردن',
    'follow_offset': 10,
  },
]

PROPERTIES = [
  {
    'title': 'آپارتمان ۱۲۰ متری جردن — نوساز',
    'property_type': 'آپارتمان',
    'deal_mode': 'فروش',
    'transaction_status': 'فعال',
    'publish_status': 'منتشرشده',
    'area': 120,
    'rooms': '۳',
    'floor': 4,
    'total_floors': 6,
    'has_parking': True,
    'has_storage': True,
    'has_elevator': True,
    'build_year': 1401,
    'sale_price': 12_500_000_000,
    'district_idx': 0,
    'token': 'demo-jordan-120',
  },
  {
    'title': 'ویلای ۲۵۰ متری لواسان',
    'property_type': 'ویلا',
    'deal_mode': 'رهن و اجاره',
    'transaction_status': 'در مذاکره',
    'publish_status': 'منتشرشده',
    'area': 250,
    'rooms': '۴',
    'floor': 2,
    'total_floors': 2,
    'has_parking': True,
    'has_storage': True,
    'has_elevator': False,
    'build_year': 1395,
    'deposit': 500_000_000,
    'monthly_rent': 28_000_000,
    'district_idx': 1,
    'token': 'demo-lavasan-villa',
  },
  {
    'title': 'آپارتمان ۸۵ متری پاسداران',
    'property_type': 'آپارتمان',
    'deal_mode': 'فروش',
    'transaction_status': 'قرارداد',
    'publish_status': 'مخفی',
    'area': 85,
    'rooms': '۲',
    'floor': 3,
    'total_floors': 5,
    'has_parking': True,
    'has_storage': False,
    'has_elevator': True,
    'build_year': 1398,
    'sale_price': 9_800_000_000,
    'district_idx': 2,
    'token': 'demo-pasdaran-85',
  },
  {
    'title': 'آپارتمان ۹۵ متری سعادت‌آباد — اجاره',
    'property_type': 'آپارتمان',
    'deal_mode': 'اجاره',
    'transaction_status': 'فعال',
    'publish_status': 'منتشرشده',
    'area': 95,
    'rooms': '۲',
    'floor': 7,
    'total_floors': 10,
    'has_parking': True,
    'has_storage': True,
    'has_elevator': True,
    'build_year': 1400,
    'deposit': 300_000_000,
    'monthly_rent': 20_000_000,
    'district_idx': 3,
    'token': 'demo-saadat-95',
  },
  {
    'title': 'زمین ۵۰۰ متری شمال شهر',
    'property_type': 'زمین',
    'deal_mode': 'فروش',
    'transaction_status': 'فعال',
    'publish_status': 'پیش‌نویس',
    'area': 500,
    'sale_price': 25_000_000_000,
    'district_idx': 1,
    'token': 'demo-land-north',
  },
  {
    'title': 'واحد اداری ۱۵۰ متری مرکز شهر',
    'property_type': 'اداری',
    'deal_mode': 'فروش',
    'transaction_status': 'فروخته‌شده',
    'publish_status': 'بایگانی',
    'area': 150,
    'rooms': '—',
    'floor': 12,
    'total_floors': 20,
    'has_parking': True,
    'has_elevator': True,
    'build_year': 1390,
    'sale_price': 18_000_000_000,
    'district_idx': 4,
    'token': 'demo-office-150',
  },
  {
    'title': 'مغازه ۴۰ متری نارمک',
    'property_type': 'مغازه',
    'deal_mode': 'رهن و اجاره',
    'transaction_status': 'اجاره‌رفته',
    'publish_status': 'بایگانی',
    'area': 40,
    'deposit': 800_000_000,
    'monthly_rent': 35_000_000,
    'district_idx': 5,
    'token': 'demo-shop-narmak',
  },
]

COORDS = [
    (35.7575, 51.4160),
    (35.8100, 51.4700),
    (35.7810, 51.4700),
    (35.7740, 51.3750),
    (35.7320, 51.4100),
    (35.7240, 51.4900),
    (35.7320, 51.5200),
    (35.8550, 50.9700),
]


class Command(BaseCommand):
    help = 'ایجاد داده‌های نمایشی CRM برای تست تمام قابلیت‌ها'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default='qashqaeii',
            help='نام کاربری (پیش‌فرض: qashqaeii)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='حذف داده‌های CRM قبلی این کاربر قبل از ایجاد',
        )

    def handle(self, *args, **options):
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'کاربر «{username}» یافت نشد.'))
            return

        self.stdout.write(self.style.SUCCESS(f'کاربر «{username}» — شروع seed داده CRM...\n'))

        if options['clear']:
            self._clear_crm_data(user)
            self.stdout.write(self.style.WARNING('داده‌های CRM قبلی حذف شد.\n'))

        with transaction.atomic():
            settings, _ = WorkspaceSettings.objects.get_or_create(user=user)
            if not settings.agency_name:
                settings.agency_name = 'آژانس املاک نمونه'
                settings.save(update_fields=['agency_name'])

            customers = self._create_customers(user)
            properties = self._create_properties(user)
            self._link_contacts(customers, properties)
            self._create_deals(user, customers, properties)
            self._create_visits(user, customers, properties)
            self._create_reminders(user, customers)
            self._create_activities(customers, properties)
            self._create_listings(customers, properties)
            self._create_documents(user, customers, properties)
            self._create_templates_and_automation(user)

        self._print_summary(user)

    def _clear_crm_data(self, user):
        CRMDeal.objects.filter(user=user).delete()
        PropertyVisit.objects.filter(user=user).delete()
        Reminder.objects.filter(user=user).delete()
        CustomerDocument.objects.filter(user=user).delete()
        CRMAutomationRule.objects.filter(user=user).delete()
        CRMMessageTemplate.objects.filter(user=user).delete()
        Customer.objects.filter(user=user).delete()
        CRMProperty.objects.filter(user=user).delete()

    def _create_customers(self, user):
        today = timezone.now().date()
        created = []
        lead_customer = None

        for i, data in enumerate(CONTACTS):
            city, district, neighborhood = TEHRAN_DISTRICTS[i % len(TEHRAN_DISTRICTS)]
            follow_offset = data.pop('follow_offset', None)
            from_lead = data.pop('from_lead', False)

            customer = Customer.objects.create(
                user=user,
                city=city,
                district=district,
                **data,
            )
            if follow_offset is not None:
                customer.next_follow_up = today + timedelta(days=follow_offset)
                customer.save(update_fields=['next_follow_up'])

            days_ago = random.randint(1, 45)
            Customer.objects.filter(pk=customer.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago),
                updated_at=timezone.now() - timedelta(hours=random.randint(1, 72)),
            )
            customer.refresh_from_db()

            if from_lead and lead_customer is None:
                lead_customer = Customer.objects.create(
                    user=user,
                    name='سرنخ قدیمی کامران',
                    phone='09120000000',
                    customer_type='سرنخ',
                    status='بایگانی',
                    source='دیوار',
                    city='تهران',
                    district='منطقه ۳',
                )
                customer.converted_from = lead_customer
                customer.save(update_fields=['converted_from'])
            elif customer.customer_type == 'سرنخ':
                lead_customer = customer

            created.append(customer)

        return created

    def _create_properties(self, user):
        props = []
        for i, data in enumerate(PROPERTIES):
            district_idx = data.pop('district_idx', i % len(TEHRAN_DISTRICTS))
            city, district, neighborhood = TEHRAN_DISTRICTS[district_idx]
            lat, lng = COORDS[district_idx % len(COORDS)]

            prop = CRMProperty.objects.create(
                user=user,
                city=city,
                district=district,
                neighborhood=neighborhood,
                address=f'{neighborhood}، {district}، {city}',
                latitude=lat + random.uniform(-0.01, 0.01),
                longitude=lng + random.uniform(-0.01, 0.01),
                link=f'https://divar.ir/v/demo-{i + 1}',
                amenities='آسانسور، پارکینگ، انباری',
                notes='ملک نمایشی برای تست CRM.',
                **data,
            )
            days_ago = random.randint(2, 60)
            CRMProperty.objects.filter(pk=prop.pk).update(
                created_at=timezone.now() - timedelta(days=days_ago),
            )
            prop.refresh_from_db()
            props.append(prop)
        return props

    def _link_contacts(self, customers, properties):
        links = [
            (0, 0, 'خریدار', 'خرید', 'بالا', True),
            (1, 2, 'فروشنده', 'فروش', 'بالا', True),
            (2, 1, 'مالک', 'رهن و اجاره', 'بالا', True),
            (3, 3, 'مستاجر', 'اجاره', 'متوسط', True),
            (4, 3, 'موجر', 'رهن و اجاره', 'بالا', True),
            (5, 4, 'سرمایه‌گذار', 'سرمایه‌گذاری', 'بالا', False),
            (0, 3, 'پیشنهادی', 'اجاره', 'متوسط', False),
            (9, 0, 'فروشنده', 'فروش', 'بالا', True),
            (10, 5, 'خریدار', 'خرید', 'بالا', True),
            (11, 0, 'خریدار', 'خرید', 'بالا', True),
        ]
        for ci, pi, role, deal_type, interest, is_primary in links:
            PropertyContact.objects.get_or_create(
                customer=customers[ci],
                property=properties[pi],
                role=role,
                defaults={
                    'deal_type': deal_type,
                    'interest_level': interest,
                    'is_primary': is_primary,
                    'notes': 'ارتباط نمایشی',
                },
            )

    def _create_deals(self, user, customers, properties):
        today = timezone.now().date()
        deals_data = [
            ('سرنخ خرید جردن', 0, 0, 'سرنخ', 12_500_000_000, 20, 14),
            ('مذاکره ویلای لواسان', 2, 1, 'مذاکره', 500_000_000, 50, 21),
            ('بازدید پاسداران', 1, 2, 'بازدید', 9_800_000_000, 60, 10),
            ('پیش‌قرارداد سعادت‌آباد', 3, 3, 'پیش‌قرارداد', 300_000_000, 75, 7),
            ('قرارداد جردن', 13, 0, 'قرارداد', 12_000_000_000, 90, 3),
            ('فروش موفق اداری', 10, 5, 'بسته‌شده', 18_000_000_000, 100, -5),
            ('از دست رفته — قیمت بالا', 8, 0, 'از دست رفته', 12_500_000_000, 0, -10),
        ]
        for title, ci, pi, stage, value, prob, close_offset in deals_data:
            close_date = today + timedelta(days=close_offset)
            deal = CRMDeal.objects.create(
                user=user,
                customer=customers[ci],
                property=properties[pi],
                listing_token=properties[pi].token,
                title=title,
                stage=stage,
                value=value,
                probability=prob,
                expected_close_date=close_date,
                commission_rate=1.0,
                commission_amount=int(value * 0.01) if value else None,
                notes=f'معامله نمایشی — مرحله {stage}',
            )
            if stage == 'بسته‌شده':
                deal.contract_number = 'DEMO-1404-001'
                deal.contract_amount = value
                deal.contract_date = today - timedelta(days=5)
                deal.closed_at = timezone.now() - timedelta(days=5)
                deal.commission_amount = int(value * 0.01)
                deal.save()
            elif stage == 'از دست رفته':
                deal.lost_reason = LOST_REASONS[0]
                deal.closed_at = timezone.now() - timedelta(days=3)
                deal.save()

    def _create_visits(self, user, customers, properties):
        today = timezone.now().date()
        visits = [
            (0, 0, 0, 'پسندید', ''),
            (1, 2, -2, 'رد', 'قیمت'),
            (3, 3, 0, 'در انتظار', ''),
            (11, 0, 2, 'بازدید مجدد', ''),
            (8, 0, -7, 'رد', 'موقعیت'),
            (5, 4, 5, 'در انتظار', ''),
        ]
        for ci, pi, day_offset, outcome, reject in visits:
            PropertyVisit.objects.create(
                user=user,
                customer=customers[ci],
                property=properties[pi],
                listing_token=properties[pi].token,
                listing_title=properties[pi].title,
                visit_date=today + timedelta(days=day_offset),
                outcome=outcome,
                reject_reason=reject,
                notes='بازدید نمایشی',
            )

    def _create_reminders(self, user, customers):
        now = timezone.now()
        today = now.date()

        reminders = [
            ('تماس با علی رضایی', 0, -2, False, ''),
            ('پیگیری سارا موسوی', 3, 0, False, ''),
            ('یادآوری بازدید جردن', 0, 1, False, ''),
            ('ارسال پیشنهاد به مریم', 1, 3, False, ''),
            ('پیگیری هفتگی رضا نوری', 4, 7, False, 'weekly'),
            ('پیگیری ماهانه سرمایه‌گذار', 5, 14, False, 'monthly'),
            ('تماس انجام‌شده', 7, -5, True, ''),
            ('یادآور امروز عصر', 11, 0, False, ''),
        ]
        for title, ci, day_offset, is_done, recurrence in reminders:
            if day_offset == 0 and not is_done and 'عصر' in title:
                due = now.replace(hour=17, minute=30, second=0, microsecond=0)
            elif day_offset == 0:
                due = now.replace(hour=10, minute=0, second=0, microsecond=0)
            else:
                due = timezone.make_aware(
                    datetime.combine(today + timedelta(days=day_offset), datetime.min.time().replace(hour=9))
                )
            Reminder.objects.create(
                user=user,
                customer=customers[ci],
                title=title,
                note=f'یادآور نمایشی برای {customers[ci].name}',
                due_at=due,
                is_done=is_done,
                recurrence=recurrence,
            )

    def _create_activities(self, customers, properties):
        samples = [
            ('تماس', 'تماس اولیه — علاقه‌مند به بازدید.'),
            ('واتساپ', 'ارسال لیست ۳ ملک در واتساپ.'),
            ('بازدید', 'بازدید حضوری انجام شد.'),
            ('جلسه', 'جلسه حضوری در دفتر.'),
            ('یادداشت', 'مشتری به دنبال ملک نورگیر است.'),
            ('پیگیری', 'پیگیری بعدی برای هفته آینده ثبت شد.'),
            ('تغییر وضعیت', 'وضعیت از «جدید» به «در حال پیگیری» تغییر کرد.'),
            ('ایمیل', 'ارسال بروشور ملک.'),
        ]
        for i, customer in enumerate(customers[:12]):
            for j, (atype, content) in enumerate(samples[:4]):
                if atype not in ACTIVITY_TYPES:
                    continue
                prop = properties[j % len(properties)] if j % 2 == 0 else None
                act = CustomerActivity.objects.create(
                    customer=customer,
                    activity_type=atype,
                    title=atype,
                    content=content,
                    property=prop,
                    duration_minutes=random.choice([None, 5, 15, 30]),
                )
                days_ago = (i * 3) + j + 1
                CustomerActivity.objects.filter(pk=act.pk).update(
                    created_at=timezone.now() - timedelta(days=days_ago),
                )

    def _create_listings(self, customers, properties):
        listings = [
            (0, 0, 'demo-divar-001', 'آپارتمان ۱۱۰ متری جردن', '۱۱,۵۰۰,۰۰۰,۰۰۰', '۱۱۰'),
            (3, 3, 'demo-divar-002', 'اجاره آپارتمان سعادت‌آباد', '۳۰۰,۰۰۰,۰۰۰', '۹۰'),
            (5, 4, 'demo-divar-003', 'زمین ۵۰۰ متری', '۲۵,۰۰۰,۰۰۰,۰۰۰', '۵۰۰'),
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
                role='پیشنهادی',
                deal_type='خرید' if pi in (0, 4) else 'اجاره',
                notes='آگهی دیوار مرتبط — نمایشی',
            )

    def _create_documents(self, user, customers, properties):
        docs = [
            ('کارت ملی علی رضایی', customers[0], None, 'کارت ملی'),
            ('سند ملک پاسداران', customers[1], properties[2], 'سند'),
            ('قرارداد اجاره', customers[3], properties[3], 'قرارداد'),
        ]
        for title, customer, prop, doc_type in docs:
            content = ContentFile(
                f'فایل نمایشی CRM — {title}\n'.encode('utf-8'),
                name=f'demo_{customer.pk}_{doc_type}.txt',
            )
            CustomerDocument.objects.create(
                user=user,
                customer=customer,
                property=prop,
                title=title,
                file=content,
                doc_type=doc_type,
            )

    def _create_templates_and_automation(self, user):
        ensure_default_templates(user)
        CRMMessageTemplate.objects.get_or_create(
            user=user,
            name='پیامک یادآوری بازدید',
            defaults={
                'category': 'بازدید',
                'channel': 'پیامک',
                'body': '{name} عزیز، یادآوری بازدید امروز. {agency}',
                'is_system': False,
            },
        )
        CRMAutomationRule.objects.get_or_create(
            user=user,
            name='پیگیری مخاطبین غیرفعال',
            defaults={
                'is_active': True,
                'trigger': 'inactive_days',
                'trigger_days': 7,
                'trigger_statuses': 'جدید,در حال پیگیری',
                'action': 'create_reminder',
                'action_reminder_title': 'پیگیری خودکار — غیرفعال',
                'action_reminder_days': 1,
            },
        )
        CRMAutomationRule.objects.get_or_create(
            user=user,
            name='بایگانی خودکار (غیرفعال)',
            defaults={
                'is_active': False,
                'trigger': 'inactive_days',
                'trigger_days': 30,
                'trigger_statuses': 'جدید',
                'action': 'set_status',
                'action_status': 'بایگانی',
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
            'آگهی‌های مرتبط': CustomerListing.objects.filter(customer__user=user).count(),
            'مدارک': CustomerDocument.objects.filter(user=user).count(),
            'قالب پیام': CRMMessageTemplate.objects.filter(user=user).count(),
            'قوانین اتوماسیون': CRMAutomationRule.objects.filter(user=user).count(),
        }
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 50))
        self.stdout.write(self.style.SUCCESS('داده‌های نمایشی CRM با موفقیت ایجاد شد'))
        self.stdout.write(self.style.SUCCESS('=' * 50 + '\n'))
        for label, count in counts.items():
            self.stdout.write(f'  {label}: {count}')
        self.stdout.write('\nصفحات قابل بررسی:')
        self.stdout.write('  /workspace/crm/              — داشبورد')
        self.stdout.write('  /workspace/crm/today/        — کار امروز')
        self.stdout.write('  /workspace/crm/contacts/      — مخاطبین')
        self.stdout.write('  /workspace/crm/deals/         — معاملات')
        self.stdout.write('  /workspace/crm/properties/    — املاک')
        self.stdout.write('  /workspace/crm/reminders/     — یادآورها')
        self.stdout.write('  /workspace/crm/calendar/      — تقویم')
        self.stdout.write('  /workspace/crm/templates/     — قالب پیام')
        self.stdout.write('  /workspace/crm/automation/    — اتوماسیون')
        self.stdout.write('')
