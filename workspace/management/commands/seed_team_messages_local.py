"""
داده نمایشی مرکز پیام تیم — فقط توسعه لوکال.

مکالمات مستقیم + یک پیام گروهی بین مالک و اعضای آژانس.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.urls import reverse

from accounts.phone_utils import find_user_by_phone, normalize_phone
from workspace.models import CRMAgencyMember, CRMAgencyMessageThread
from workspace.services.crm_agency_messages import (
    list_threads_for_user,
    send_broadcast_message,
    send_direct_message,
    unread_message_count,
)
from workspace.services.crm_scope import agency_members, get_membership

User = get_user_model()

LOCAL_DEV_PASSWORD = 'localdev123'


class Command(BaseCommand):
    help = 'Seed نمونه مکالمات مرکز پیام تیم برای تست لوکال'

    def add_arguments(self, parser):
        parser.add_argument('--phone', default='09357930033', help='موبایل مالک آژانس')
        parser.add_argument(
            '--ensure-agency-demo',
            action='store_true',
            default=True,
            help='در صورت نیاز seed_agency_local_demo را هم اجرا کن (پیش‌فرض: بله)',
        )
        parser.add_argument(
            '--no-ensure-agency-demo',
            action='store_false',
            dest='ensure_agency_demo',
            help='فقط پیام بساز؛ مشاوران را خودتان آماده کرده‌اید',
        )
        parser.add_argument(
            '--set-password',
            action='store_true',
            default=True,
            help=f'رمز ورود مالک را روی {LOCAL_DEV_PASSWORD} بگذار (ورود password در /accounts/login/)',
        )
        parser.add_argument(
            '--no-set-password',
            action='store_false',
            dest='set_password',
        )
        parser.add_argument('--reset', action='store_true', help='حذف مکالمات قبلی همین آژانس قبل از seed')

    def handle(self, *args, **options):
        phone = normalize_phone(options['phone'])
        owner = find_user_by_phone(phone) or User.objects.filter(phone=phone).first()
        if not owner:
            raise CommandError(f'کاربر با شماره {phone} یافت نشد.')

        membership = get_membership(owner)
        if not membership and options['ensure_agency_demo']:
            self.stdout.write('عضو آژانس نیست — seed_agency_local_demo ...')
            call_command('seed_agency_local_demo', phone=phone, verbosity=1)
            membership = get_membership(owner)
        if not membership:
            raise CommandError('کاربر عضو آژانس نیست — seed_crm_demo یا seed_agency_local_demo را اجرا کنید.')

        agency = membership.agency
        members = list(agency_members(agency))
        if len(members) < 2 and options['ensure_agency_demo']:
            self.stdout.write('اعضای کافی نیست — seed_agency_local_demo ...')
            call_command('seed_agency_local_demo', phone=phone, verbosity=1)
            members = list(agency_members(agency))
        if len(members) < 2:
            raise CommandError('حداقل دو عضو فعال در آژانس لازم است.')

        owner_member = next(m for m in members if m.user_id == owner.pk)
        others = [m for m in members if m.user_id != owner.pk]

        if options['reset']:
            deleted, _ = CRMAgencyMessageThread.objects.filter(agency=agency).delete()
            self.stdout.write(self.style.WARNING(f'deleted {deleted} message-related rows'))

        with transaction.atomic():
            self._seed_conversations(owner, owner_member, others)
            if options['set_password']:
                owner.set_password(LOCAL_DEV_PASSWORD)
                owner.save(update_fields=['password'])

        items, total = list_threads_for_user(owner)
        unread = unread_message_count(owner)
        hub_url = reverse('workspace:agency_hub_messages')

        self.stdout.write(self.style.SUCCESS(
            f'OK agency={agency.pk} threads={total} unread_owner={unread}',
        ))
        for row in items[:8]:
            subj = row.get('subject') or row.get('participants_label') or '—'
            self.stdout.write(f'  • #{row["id"]} {subj} (unread={row.get("unread_count", 0)})')

        self.stdout.write('')
        self.stdout.write(f'  Hub: {hub_url}')
        if options['set_password']:
            self.stdout.write(f'  Login: {phone} / {LOCAL_DEV_PASSWORD} → /accounts/login/')

    def _seed_conversations(self, owner, owner_member, others):
        a = others[0]
        send_direct_message(
            owner,
            a.pk,
            'سلام — این پیام تست لوکال «مرکز پیام تیم» است. لیست موبایل باید این را نشان دهد.',
        )
        send_direct_message(
            a.user,
            owner_member.pk,
            'دریافت شد. پاسخ از طرف مشاور برای تست RTL و لیست.',
        )
        if len(others) > 1:
            b = others[1]
            send_direct_message(
                owner,
                b.pk,
                'پیام دوم: هماهنگی بازدید فردا ساعت ۱۰ — ملک کد ۱۲۳۴.',
            )
        send_broadcast_message(
            owner,
            'اطلاعیه تست لوکال: جلسه هماهنگی تیم فردا ۹:۳۰ در دفتر.',
            subject='جلسه هماهنگی',
            target_roles=['advisor', 'manager'],
        )
        send_direct_message(
            owner,
            a.pk,
            'پیام کوتاه بعد از broadcast — برای چند ردیف در لیست.',
        )
