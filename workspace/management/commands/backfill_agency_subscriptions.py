"""Backfill AgencySubscription از سفارش‌های paid پلن آژانس موجود."""
from __future__ import annotations

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import Order
from workspace.models import CRMAgency, AgencySubscription
from workspace.services.agency_entitlement import (
    is_agency_plan_order,
    provision_subscription_from_paid_order,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Backfill اشتراک آژانس از سفارش‌های paid با allow_bulk_purchase'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='فقط گزارش، بدون تغییر')
        parser.add_argument('--lock-free-agencies', action='store_true', help='قفل آژانس‌های بدون اشتراک')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        lock_free = options['lock_free_agencies']
        created = 0
        skipped = 0
        ambiguous = []

        orders = Order.objects.filter(status='paid').select_related('plan', 'user').order_by('paid_at')
        for order in orders:
            if not is_agency_plan_order(order):
                continue
            if AgencySubscription.objects.filter(source_order=order).exists():
                skipped += 1
                continue
            if dry_run:
                self.stdout.write(f'[dry-run] would provision order {order.pk} user={order.user_id} qty={order.quantity}')
                created += 1
                continue
            try:
                with transaction.atomic():
                    sub = provision_subscription_from_paid_order(order)
                    if sub:
                        agency = CRMAgency.objects.filter(owner=order.user).first()
                        if agency and not sub.agency_id:
                            sub.agency = agency
                            sub.save(update_fields=['agency'])
                            agency.management_status = 'active'
                            agency.save(update_fields=['management_status'])
                        created += 1
                        self.stdout.write(self.style.SUCCESS(f'provisioned order {order.pk} -> sub {sub.pk}'))
            except Exception as exc:
                ambiguous.append((order.pk, str(exc)))
                logger.exception('backfill failed order %s', order.pk)

        if lock_free:
            locked = 0
            for agency in CRMAgency.objects.all().select_related('owner'):
                from workspace.services.agency_entitlement import get_subscription_for_agency
                if not get_subscription_for_agency(agency):
                    if not dry_run:
                        agency.management_status = 'locked'
                        agency.save(update_fields=['management_status'])
                    locked += 1
            self.stdout.write(f'locked agencies: {locked}')

        self.stdout.write(f'created={created} skipped={skipped} ambiguous={len(ambiguous)}')
        for oid, err in ambiguous:
            self.stdout.write(self.style.WARNING(f'  order {oid}: {err}'))
