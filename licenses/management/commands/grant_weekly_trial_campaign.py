"""کمپین هدیه ۷ روز دسترسی حرفه‌ای — dry-run، اعطا و پیامک دسته‌ای."""
from django.core.management.base import BaseCommand, CommandError

from licenses.services.weekly_trial_campaign import (
    WeeklyTrialCampaignError,
    default_campaign_key,
    format_stats_lines,
    run_weekly_trial_campaign,
)


class Command(BaseCommand):
    help = (
        'کمپین هدیه ۷ روز دسترسی حرفه‌ای: '
        '--dry-run برای آمار، --apply برای صدور لایسنس، --send-sms برای اطلاع‌رسانی'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='فقط شناسایی و آمار — بدون تغییر دیتابیس و بدون پیامک',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='صدور و فعال‌سازی لایسنس هدیه (با کنترل تکرار)',
        )
        parser.add_argument(
            '--send-sms',
            action='store_true',
            help='ارسال پیامک برای هدایای فعال‌شده و مجاز به دریافت تبلیغات',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='سقف کاربران در این اجرا (برای تست دسته‌ای)',
        )
        parser.add_argument(
            '--campaign',
            type=str,
            default=None,
            help='شناسه یکتا کمپین (پیش‌فرض از تنظیمات)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        apply = options['apply']
        send_sms = options['send_sms']
        if not dry_run and not apply and not send_sms:
            raise CommandError('حداقل یکی از --dry-run، --apply یا --send-sms را مشخص کنید.')
        if dry_run and (apply or send_sms):
            raise CommandError('--dry-run را نمی‌توان هم‌زمان با --apply یا --send-sms استفاده کرد.')

        campaign_key = (options['campaign'] or '').strip() or default_campaign_key()
        if not campaign_key:
            raise CommandError('شناسه کمپین خالی است.')

        try:
            stats = run_weekly_trial_campaign(
                campaign_key=campaign_key,
                dry_run=dry_run,
                apply=apply,
                send_sms=send_sms,
                limit=options['limit'],
            )
        except WeeklyTrialCampaignError as exc:
            raise CommandError(str(exc)) from exc

        prefix = '[dry-run] ' if dry_run else ''
        for line in format_stats_lines(stats):
            self.stdout.write(prefix + line)
