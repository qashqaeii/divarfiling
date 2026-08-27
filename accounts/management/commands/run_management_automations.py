"""Runner مرکزی Automation دستیار مدیریت."""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from accounts.services.admin_management_assistant import ensure_automation_rules
from accounts.services.management_automation_runner import run_management_automations


class Command(BaseCommand):
    help = (
        'اجرای Automationهای فعال دستیار مدیریت. '
        'پیشنهاد cron: هر ساعت. Ruleهای daily بیش از یک بار در روز اجرا نمی‌شوند.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='بدون SMS واقعی — فقط log و dry_run recipient',
        )
        parser.add_argument(
            '--rule-key',
            type=str,
            default='',
            help='اجرای فقط یک Rule',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='نادیده گرفتن cadence (تست)',
        )

    def handle(self, *args, **options):
        ensure_automation_rules()
        dry_run = bool(options.get('dry_run'))
        rule_key = (options.get('rule_key') or '').strip() or None
        force = bool(options.get('force'))

        if rule_key:
            from accounts.models import ManagementAutomationRule
            if not ManagementAutomationRule.objects.filter(key=rule_key).exists():
                raise CommandError(f'Rule نامعتبر: {rule_key}')

        summary = run_management_automations(
            dry_run=dry_run,
            rule_key=rule_key,
            force=force,
        )

        self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, default=str))

        if summary.get('errors'):
            self.stderr.write(self.style.WARNING(
                f"{len(summary['errors'])} rule با خطا — بقیه ادام یافت.",
            ))

        self.stdout.write(self.style.SUCCESS(
            f"examined={summary['rules_examined']} "
            f"run={summary['rules_run']} skipped={summary['rules_skipped']}",
        ))
