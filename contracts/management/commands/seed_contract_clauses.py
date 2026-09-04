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
from contracts.services.lease_clause_bank import (
    LEASE_DEPRECATED_CODES,
    LEASE_PHASE1_DEFINITIONS,
)
from contracts.services.sale_clause_bank import (
    SALE_DEPRECATED_CODES,
    SALE_PHASE1_DEFINITIONS,
)

JV_CATEGORIES = [
    ('JV_CONTRIBUTION_OWNER', 'آورده مالک', 'آورده مالک شامل ملک به ارزش {owner_property_value} است.'),
    ('JV_CONTRIBUTION_BUILDER', 'آورده سازنده', 'آورده سازنده شامل هزینه ساخت و جواز است.'),
    ('JV_SHARE', 'قدرالسهم', 'سهم مالک {owner_percent}% و سازنده {builder_percent}% است.'),
    ('JV_UNITS', 'تقسیم واحدها', 'تخصیص واحدها طبق پیوست.'),
    ('JV_SCHEDULE', 'زمان‌بندی', 'زمان‌بندی پروژه طبق جدول مراحل است.'),
    ('JV_PENALTY', 'وجه التزام تأخیر', 'تأخیر مشمول جریمه روزانه است.'),
    ('JV_DISPUTE', 'حل اختلاف', 'اختلاف از طریق داوری حل می‌شود.'),
]

LEASE_CORE_SEED = [
    ('LEASE_SUBJECT', 'موضوع قرارداد', 'subject', 'موضوع این قرارداد، اجاره {property_type} واقع در {address} می‌باشد.'),
    ('LEASE_TERM', 'مدت', 'term', 'مدت اجاره از {lease_start} تا {lease_end} است.'),
    ('LEASE_DEPOSIT', 'ودیعه', 'financial', 'مبلغ قرض‌الحسنه/ودیعه مبلغ {deposit} تومان است.'),
    ('LEASE_RENT', 'اجاره‌بها', 'financial', 'اجاره ماهانه مبلغ {monthly_rent} تومان است.'),
    ('LEASE_PAYMENT', 'نحوه پرداخت', 'payment', 'اجاره‌بها تا روز {rent_payment_day} هر ماه پرداخت می‌شود.'),
    ('LEASE_RENT_PAYMENT', 'پرداخت اجاره‌بها', 'payment', (
        'مستأجر متعهد است اجاره‌بهای ماهانه به مبلغ {{monthly_rent}} تومان را در موعد تعیین‌شده '
        'یعنی روز {{rent_due_day}} هر ماه، از طریق روش پرداخت مورد توافق طرفین پرداخت نماید.'
    )),
]

SALE_CORE_SEED = [
    ('SALE_SUBJECT', 'موضوع معامله', 'subject', 'فروش {property_type} واقع در {address}'),
    ('SALE_PRICE', 'ثمن معامله', 'financial', 'ثمن کل {total_price} تومان است.'),
    ('SALE_PAYMENT', 'نحوه پرداخت', 'payment', 'پرداخت طبق جدول اقساط پیوست انجام می‌شود.'),
    ('SALE_TRANSFER', 'انتقال رسمی', 'official_transfer', 'مراجعه برای انتقال رسمی در {official_transfer_date}.'),
]


class Command(BaseCommand):
    help = 'Seed contract clause definitions and legal rules (review_pending)'

    def handle(self, *args, **options):
        src_civil, _ = ContractLegalSource.objects.get_or_create(
            code='CIVIL_CODE',
            defaults={'title': 'قانون مدنی', 'article': 'ماده ۱۰'},
        )
        src_lease, _ = ContractLegalSource.objects.get_or_create(
            code='LANDLORD_TENANT',
            defaults={'title': 'قانون روابط موجر و مستأجر ۱۳۷۶ (اصلاح ۱۴۰۳)'},
        )
        ContractLegalSource.objects.get_or_create(
            code='E_COMMERCE',
            defaults={'title': 'قانون تجارت الکترونیکی', 'article': 'مواد ۶ تا ۱۵'},
        )

        sources = {'CIVIL_CODE': src_civil, 'LANDLORD_TENANT': src_lease}

        for code, title, category, body in LEASE_CORE_SEED:
            ContractClauseDefinition.objects.update_or_create(
                code=code, version=1,
                defaults={
                    'title': title, 'category': category, 'contract_type': CONTRACT_TYPE_LEASE,
                    'body_template': body,
                    'plain_explanation': 'ماده اصلی — از داده‌های ویزارد تولید می‌شود.',
                    'is_active': False,
                    'is_recommended': False,
                    'is_optional': False,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src_lease if category != 'subject' else src_civil,
                },
            )

        lease_count = 0
        for item in LEASE_PHASE1_DEFINITIONS:
            src = sources.get(item.get('legal_source_code', 'CIVIL_CODE'), src_civil)
            ContractClauseDefinition.objects.update_or_create(
                code=item['code'], version=1,
                defaults={
                    'title': item['title'],
                    'category': item['category'],
                    'contract_type': CONTRACT_TYPE_LEASE,
                    'body_template': item['body_template'],
                    'plain_explanation': item.get('plain_explanation', ''),
                    'condition_expression': item.get('condition_expression', {}),
                    'is_required': item.get('is_required', False),
                    'is_recommended': item.get('is_recommended', True),
                    'is_optional': item.get('is_optional', True),
                    'is_active': True,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src,
                    'legal_reference': item.get('legal_reference', ''),
                    'legal_note': item.get('legal_note', ''),
                },
            )
            lease_count += 1

        ContractClauseDefinition.objects.filter(
            code__in=LEASE_DEPRECATED_CODES, contract_type=CONTRACT_TYPE_LEASE,
        ).update(is_active=False, review_status=CLAUSE_REVIEW_PENDING)

        for code, title, category, body in SALE_CORE_SEED:
            ContractClauseDefinition.objects.update_or_create(
                code=code, version=1,
                defaults={
                    'title': title, 'category': category, 'contract_type': CONTRACT_TYPE_SALE,
                    'body_template': body,
                    'plain_explanation': 'ماده اصلی — از داده‌های ویزارد تولید می‌شود.',
                    'is_active': False,
                    'is_recommended': False,
                    'is_optional': False,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src_civil,
                },
            )

        sale_count = 0
        for item in SALE_PHASE1_DEFINITIONS:
            src = sources.get(item.get('legal_source_code', 'CIVIL_CODE'), src_civil)
            ContractClauseDefinition.objects.update_or_create(
                code=item['code'], version=1,
                defaults={
                    'title': item['title'],
                    'category': item['category'],
                    'contract_type': CONTRACT_TYPE_SALE,
                    'body_template': item['body_template'],
                    'plain_explanation': item.get('plain_explanation', ''),
                    'condition_expression': item.get('condition_expression', {}),
                    'is_required': item.get('is_required', False),
                    'is_recommended': item.get('is_recommended', True),
                    'is_optional': item.get('is_optional', True),
                    'is_active': True,
                    'review_status': CLAUSE_REVIEW_PENDING,
                    'legal_source': src,
                    'legal_reference': item.get('legal_reference', ''),
                },
            )
            sale_count += 1

        ContractClauseDefinition.objects.filter(
            code__in=SALE_DEPRECATED_CODES, contract_type=CONTRACT_TYPE_SALE,
        ).update(is_active=False, review_status=CLAUSE_REVIEW_PENDING)

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

        self.stdout.write(self.style.SUCCESS(
            f'Clause banks synced (all review_pending). '
            f'Lease: {lease_count} active. Sale: {sale_count} active.',
        ))
