"""ممیزی read-only ناسازگاری agency در مخاطبین CRM."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count

from workspace.models import CRMAgencyMember, Customer
from workspace.services.crm_contact_archive import archived_contacts_q
from workspace.services.crm_scope import customers_qs, get_membership

User = get_user_model()


class Command(BaseCommand):
    help = 'گزارش Dry Run ناسازگاری agency/مالکیت مخاطبین (بدون تغییر داده).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='محدود کردن گزارش به یک کاربر',
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        self.stdout.write(self.style.MIGRATE_HEADING('ممیزی مخاطبین CRM — Dry Run'))

        member_user_ids = set(
            CRMAgencyMember.objects.filter(is_active=True).values_list('user_id', flat=True)
        )

        qs = Customer.objects.all()
        if user_id:
            qs = qs.filter(user_id=user_id)

        agency_null_member = qs.filter(user_id__in=member_user_ids, agency__isnull=True)
        self.stdout.write(
            f'مخاطبین کاربران عضو آژانس با agency=NULL: {agency_null_member.count()}'
        )

        archived_null = agency_null_member.filter(archived_contacts_q())
        self.stdout.write(f'  از آن‌ها بایگانی‌شده: {archived_null.count()}')

        legacy_personal = qs.filter(agency__isnull=True).exclude(user_id__in=member_user_ids)
        self.stdout.write(f'مخاطبین شخصی قدیمی (بدون عضویت آژانس، agency=NULL): {legacy_personal.count()}')

        invisible_import_estimate = 0
        sample_users = member_user_ids
        if user_id:
            sample_users = {user_id} & member_user_ids

        for uid in sample_users:
            user = User.objects.filter(pk=uid).first()
            if not user:
                continue
            m = get_membership(user)
            if not m:
                continue
            owned_null = Customer.objects.filter(user_id=uid, agency__isnull=True)
            visible = customers_qs(user).filter(user_id=uid).count()
            owned_total = Customer.objects.filter(user_id=uid).count()
            gap = owned_null.count()
            if gap:
                invisible_import_estimate += gap
                self.stdout.write(
                    f'  user_id={uid}: {gap} رکورد agency=NULL — '
                    f'قابل مشاهده در customers_qs: {visible}/{owned_total}'
                )

        self.stdout.write(
            f'تخمین مخاطبین احتمالاً نامرئی (agency=NULL عضو آژانس): {invisible_import_estimate}'
        )

        cross_agency = (
            Customer.objects.filter(agency__isnull=False)
            .exclude(user_id__in=member_user_ids)
            .count()
        )
        self.stdout.write(f'رکورد با agency ولی کاربر بدون عضویت فعال: {cross_agency}')

        dup_agency_users = (
            Customer.objects.filter(agency__isnull=False)
            .values('user_id', 'agency_id')
            .annotate(c=Count('id'))
            .filter(c__gt=0)
        )
        self.stdout.write(f'گروه‌های user/agency (نمونه آماری): {dup_agency_users.count()}')

        self.stdout.write(self.style.SUCCESS('پایان Dry Run — هیچ داده‌ای تغییر نکرد.'))
