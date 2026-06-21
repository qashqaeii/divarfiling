"""Expire or restore licenses for local QA. Usage:
  python manage.py expire_license_test
  python manage.py expire_license_test --expire
  python manage.py expire_license_test --restore
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from licenses.models import License, LicenseActivation


class Command(BaseCommand):
    help = "Show / expire / restore bot licenses for testing expired state"

    def add_arguments(self, parser):
        parser.add_argument(
            "--expire",
            action="store_true",
            help="Set all licenses to expired (yesterday) and status=expired",
        )
        parser.add_argument(
            "--restore",
            action="store_true",
            help="Restore all licenses to active with +30 days expiry",
        )
        parser.add_argument(
            "--key",
            type=str,
            default="",
            help="Only affect this license key (optional)",
        )

    def handle(self, *args, **options):
        qs = License.objects.select_related("order__user", "plan").all()
        if options["key"]:
            qs = qs.filter(license_key=options["key"].strip().upper())

        if not qs.exists():
            self.stderr.write(self.style.ERROR("No license found."))
            return

        self._print_licenses(qs)

        if options["expire"]:
            past = timezone.now() - timedelta(days=1)
            for lic in qs:
                lic.expires_at = past
                lic.status = "expired"
                lic.save(update_fields=["expires_at", "status"])
                self.stdout.write(
                    self.style.WARNING(f"Expired: {lic.license_key} (was valid until test)")
                )
            self.stdout.write(self.style.SUCCESS(f"Expired {qs.count()} license(s)."))
            self.stdout.write("")
            self._print_licenses(qs)
            self._print_test_hints()
        elif options["restore"]:
            future = timezone.now() + timedelta(days=30)
            for lic in qs:
                lic.expires_at = future
                lic.status = "active"
                lic.save(update_fields=["expires_at", "status"])
                self.stdout.write(self.style.SUCCESS(f"Restored: {lic.license_key}"))
        elif not options["expire"] and not options["restore"]:
            self.stdout.write("Use --expire to simulate expiry, or --restore to undo.")

    def _print_licenses(self, qs):
        self.stdout.write(f"Licenses: {qs.count()}")
        for lic in qs:
            acts = LicenseActivation.objects.filter(license=lic, is_active=True).count()
            user = lic.order.user.username if lic.order_id else "—"
            plan = lic.plan.name if lic.plan_id else "—"
            self.stdout.write(
                f"  [{lic.license_key}] status={lic.status} valid={lic.is_valid()} "
                f"expires={lic.expires_at} user={user} plan={plan} devices={acts}"
            )

    def _print_test_hints(self):
        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("--- What to test ---"))
        self.stdout.write("App: restart extractor-app, or click «بررسی مجدد» on License tab.")
        self.stdout.write("API: POST /api/licenses/validate/ should return valid=false.")
        self.stdout.write("Web: workspace bot features lock; dashboard shows expired state.")
