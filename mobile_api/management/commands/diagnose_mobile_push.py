"""تشخیص Push موبایل — وضعیت FCM token، Firebase server، و ارسال تست."""
from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from mobile_api.models import MobileDevice
from mobile_api.services.push_service import _get_v1_access_token, send_push_to_user

User = get_user_model()


class Command(BaseCommand):
    help = 'بررسی push موبایل (FCM token، service account) و ارسال اعلان تست'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            required=True,
            help='نام کاربری divarfiling.ir',
        )
        parser.add_argument(
            '--send-test',
            action='store_true',
            help='یک push تست به دستگاه‌های این کاربر بفرست',
        )

    def handle(self, *args, **options):
        username = options['username']
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f'کاربر یافت نشد: {username}')

        self.stdout.write(self.style.MIGRATE_HEADING('=== Firebase server (Django) ==='))
        project_id = getattr(settings, 'FCM_PROJECT_ID', '') or 'divarfiling'
        sa_path = getattr(settings, 'FCM_SERVICE_ACCOUNT_FILE', '') or ''
        self.stdout.write(f'FCM_PROJECT_ID: {project_id}')
        self.stdout.write(f'FCM_SERVICE_ACCOUNT_FILE: {sa_path}')
        if not sa_path:
            self.stdout.write(self.style.ERROR('مسیر service account تنظیم نشده — push از سرور کار نمی‌کند.'))
        elif not os.path.isfile(sa_path):
            self.stdout.write(self.style.ERROR('فایل service account روی دیسک وجود ندارد — push کار نمی‌کند.'))
        else:
            self.stdout.write(self.style.SUCCESS('فایل service account موجود است.'))
            token = _get_v1_access_token()
            if token:
                self.stdout.write(self.style.SUCCESS('دریافت access token FCM v1: OK'))
            else:
                self.stdout.write(self.style.ERROR('دریافت access token FCM v1: FAIL (لاگ سرور را ببینید)'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'=== دستگاه‌های {username} ==='))
        devices = MobileDevice.objects.filter(user=user).order_by('-last_seen_at')
        if not devices.exists():
            self.stdout.write(self.style.WARNING('هیچ MobileDevice ثبت نشده — اپ را باز کنید و login کنید.'))
            return

        has_token = False
        for dev in devices:
            token_ok = bool((dev.fcm_token or '').strip())
            if token_ok:
                has_token = True
            preview = (dev.fcm_token[:24] + '…') if token_ok else '(خالی)'
            status = self.style.SUCCESS('token OK') if token_ok else self.style.ERROR('token خالی')
            self.stdout.write(
                f'  device_id={dev.device_id[:16]}… model={dev.device_model or "?"} '
                f'app={dev.app_version or "?"} last_seen={dev.last_seen_at:%Y-%m-%d %H:%M} '
                f'fcm={preview} [{status}]',
            )

        self.stdout.write('')
        if not has_token:
            self.stdout.write(self.style.ERROR(
                'علت محتمل: fcm_token خالی است → push نمی‌رسد؛ فقط in-app از API می‌آید.\n'
                '  روی گوشی: Logout → Login (release APK) + اجازه notification.',
            ))
        elif not options['send_test']:
            self.stdout.write(
                'برای تست push: python manage.py diagnose_mobile_push '
                f'--username {username} --send-test',
            )

        if options['send_test']:
            if not has_token:
                raise CommandError('fcm_token خالی است — ابتدا login از اپ release.')
            sent = send_push_to_user(
                user,
                title='تست push دیوار فایلینگ',
                body='اگر این را می‌بینید، FCM از سرور تا گوشی کار می‌کند.',
                data={'type': 'test', 'deep_link': 'divarfiling://home'},
            )
            if sent:
                self.stdout.write(self.style.SUCCESS(f'push تست ارسال شد به {sent} دستگاه.'))
            else:
                self.stdout.write(self.style.ERROR(
                    'push تست ارسال نشد — service account یا token نامعتبر (لاگ FCM را ببینید).',
                ))
