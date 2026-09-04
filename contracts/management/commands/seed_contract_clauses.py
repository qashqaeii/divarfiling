"""Seed clause library and legal rules — همه بندها review_pending."""
from django.core.management.base import BaseCommand

from contracts.constants import (
    CLAUSE_REVIEW_PENDING,
    CONTRACT_TYPE_JV,
    CONTRACT_TYPE_LEASE,
    CONTRACT_TYPE_SALE,
    RULE_LEASE_REQUIRES_DEPOSIT,
    RULE_LEASE_REQUIRES_DURATION,
    RULE_LEASE_REQUIRES_RENT,
    RULE_LEASE_REQUIRES_WITNESSES,
)
from contracts.models import ContractClauseDefinition, ContractLegalRule, ContractLegalSource


LEASE_CATEGORIES = [
    ('LEASE_SUBJECT', 'موضوع قرارداد', 'موضوع این قرارداد، اجاره {property_type} واقع در {address} می‌باشد.'),
    ('LEASE_TERM', 'مدت', 'مدت اجاره از {lease_start} تا {lease_end} به مدت {duration_months} ماه است.'),
    ('LEASE_DEPOSIT', 'ودیعه', 'مبلغ قرض‌الحسنه/ودیعه مبلغ {deposit} تومان است.'),
    ('LEASE_RENT', 'اجاره‌بها', 'اجاره ماهانه مبلغ {monthly_rent} تومان است.'),
    ('LEASE_PAYMENT', 'نحوه پرداخت', 'اجاره‌بها تا روز {rent_payment_day} هر ماه پرداخت می‌شود.'),
    ('LEASE_DELIVERY', 'تحویل ملک', 'موجر متعهد است ملک را در تاریخ {delivery_date} تحویل دهد.'),
    ('LEASE_VACATE', 'تخلیه', 'مستأجر متعهد است در پایان مدت یا فسخ، ملک را تخلیه نماید.'),
    ('LEASE_UTILITIES', 'آب و برق و گاز', 'هزینه انشعابات طبق توافق طرفین تقسیم می‌شود.'),
    ('LEASE_REPAIRS', 'تعمیرات', 'تعمیرات اساسی بر عهده موجر و جزئی بر عهده مستأجر است.'),
    ('LEASE_SUBLEASE', 'واگذاری', 'مستأجر بدون اجازه کتبی موجر حق واگذاری به غیر ندارد.'),
    ('LEASE_PENALTY', 'وجه التزام', 'تأخیر در پرداخت مشمول وجه التزام روزانه {daily_penalty} تومان است.'),
    ('LEASE_DISPUTE', 'حل اختلاف', 'اختلافات از طریق داوری یا مراجع قضایی حل می‌شود.'),
]

SALE_CATEGORIES = [
    ('SALE_SUBJECT', 'موضوع معامله', 'فروش {property_type} واقع در {address}'),
    ('SALE_PRICE', 'ثمن معامله', 'ثمن کل {total_price} تومان است.'),
    ('SALE_PAYMENT', 'نحوه پرداخت', 'پرداخت طبق جدول اقساط پیوست انجام می‌شود.'),
    ('SALE_DELIVERY', 'تحویل', 'تحویل در تاریخ {delivery_date} انجام می‌شود.'),
    ('SALE_TRANSFER', 'انتقال رسمی', 'مراجعه برای انتقال رسمی در {official_transfer_date}.'),
    ('SALE_MORTGAGE', 'رهن', 'وضعیت رهن: {mortgage_status}'),
    ('SALE_TAX', 'مالیات', 'مالیات نقل و انتقال طبق قانون بر عهده طرفین است.'),
    ('SALE_DISPUTE', 'حل اختلاف', 'اختلاف از طریق مراجع صالح حل می‌شود.'),
]

JV_CATEGORIES = [
    ('JV_CONTRIBUTION_OWNER', 'آورده مالک', 'آورده مالک شامل ملک به ارزش {owner_property_value} است.'),
    ('JV_CONTRIBUTION_BUILDER', 'آورده سازنده', 'آورده سازنده شامل هزینه ساخت و جواز است.'),
    ('JV_SHARE', 'قدرالسهم', 'سهم مالک {owner_percent}% و سازنده {builder_percent}% است.'),
    ('JV_UNITS', 'تقسیم واحدها', 'تخصیص واحدها طبق پیوست.'),
    ('JV_SCHEDULE', 'زمان‌بندی', 'زمان‌بندی پروژه طبق جدول مراحل است.'),
    ('JV_PENALTY', 'وجه التزام تأخیر', 'تأخیر مشمول جریمه روزانه است.'),
    ('JV_DISPUTE', 'حل اختلاف', 'اختلاف از طریق داوری حل می‌شود.'),
]


class Command(BaseCommand):
    help = 'Seed contract clause definitions and legal rules (review_pending)'

    def handle(self, *args, **options):
        src_civil, _ = ContractLegalSource.objects.get_or_create(
            code='CIVIL_CODE',
            defaults={'title': 'قانون مدنی', 'article': 'ماده ۱۰، ۱۹۰'},
        )
        src_lease, _ = ContractLegalSource.objects.get_or_create(
            code='LANDLORD_TENANT',
            defaults={'title': 'قانون روابط موجر و مستأجر'},
        )
        src_ecommerce, _ = ContractLegalSource.objects.get_or_create(
            code='E_COMMERCE',
            defaults={'title': 'قانون تجارت الکترونیکی', 'article': 'مواد ۶ تا ۱۵'},
        )

        for code, cat, body in LEASE_CATEGORIES:
            ContractClauseDefinition.objects.update_or_create(
                code=code, version=1,
                defaults={
                    'title': cat, 'category': cat, 'contract_type': CONTRACT_TYPE_LEASE,
                    'body_template': body,
                    'plain_explanation': f'توضیح ساده بند {cat} — نیازمند تأیید وکیل.',
                    'is_recommended': True,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src_lease,
                    'legal_reference': 'قانون روابط موجر و مستأجر',
                },
            )

        for code, cat, body in SALE_CATEGORIES:
            ContractClauseDefinition.objects.update_or_create(
                code=code, version=1,
                defaults={
                    'title': cat, 'category': cat, 'contract_type': CONTRACT_TYPE_SALE,
                    'body_template': body,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src_civil,
                },
            )

        for code, cat, body in JV_CATEGORIES:
            ContractClauseDefinition.objects.update_or_create(
                code=code, version=1,
                defaults={
                    'title': cat, 'category': cat, 'contract_type': CONTRACT_TYPE_JV,
                    'body_template': body,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src_civil,
                },
            )

        rules = [
            (RULE_LEASE_REQUIRES_DURATION, 'الزام مدت اجاره', CONTRACT_TYPE_LEASE, 'validation'),
            (RULE_LEASE_REQUIRES_RENT, 'الزام مبلغ اجاره', CONTRACT_TYPE_LEASE, 'validation'),
            (RULE_LEASE_REQUIRES_DEPOSIT, 'الزام ودیعه', CONTRACT_TYPE_LEASE, 'validation'),
            (RULE_LEASE_REQUIRES_WITNESSES, 'الزام دو شاهد', CONTRACT_TYPE_LEASE, 'validation'),
        ]
        for code, name, ctype, rtype in rules:
            ContractLegalRule.objects.update_or_create(
                code=code,
                defaults={
                    'name': name, 'contract_type': ctype, 'rule_type': rtype,
                    'status': 'active', 'source_title': 'قانون روابط موجر و مستأجر',
                },
            )

        self.stdout.write(self.style.SUCCESS('Clause library and legal rules seeded (review_pending).'))
