"""
داده و اشتراک آژانس برای تست لوکال — فقط محیط توسعه.

- اشتراک AgencySubscription فعال + صندلی
- مشاوران نمایشی + تخصیص seat
- انتشار نمونه در Agency Space
- رویداد فعالیت نمونه
"""
from __future__ import annotations

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.phone_utils import find_user_by_phone, normalize_phone
from licenses.models import License
from shop.models import LicensePlan, Order, Product
from shop.services.order_fulfillment import fulfill_order_after_payment
from workspace.models import (
    AgencySpaceItem,
    CRMAgency,
    CRMAgencyMember,
    CRMProperty,
    Customer,
)
from workspace.services.agency_activity import (
    EVENT_CONTACT_CREATED,
    EVENT_PROPERTY_CREATED,
    EVENT_SPACE_ITEM_PUBLISHED,
    emit_agency_activity,
)
from workspace.services.agency_entitlement import (
    get_active_subscription_for_owner,
    get_subscription_for_agency,
    link_agency_to_subscription,
    provision_subscription_from_paid_order,
)
from workspace.services.agency_onboarding import mark_agency_onboarding_complete
from workspace.services.agency_seats import assign_seat_to_member
from workspace.services.agency_space_publish import publish_customer, publish_property
from workspace.services.crm_scope import get_membership

User = get_user_model()

DEMO_ADVISORS = [
    ('09120000041', 'علی رضایی', 'advisor'),
    ('09120000042', 'مینا کاظمی', 'advisor'),
    ('09120000043', 'رضا نوری', 'manager'),
]


class Command(BaseCommand):
    help = 'فعال‌سازی اشتراک آژانس + مشاوران و داده نمایشی Space برای تست لوکال'

    def add_arguments(self, parser):
        parser.add_argument('--phone', default='09357930033', help='موبایل مالک آژانس')
        parser.add_argument('--seats', type=int, default=5, help='تعداد صندلی اشتراک')
        parser.add_argument('--force-sub', action='store_true', help='اشتراک جدید حتی اگر فعال باشد')

    def handle(self, *args, **options):
        phone = normalize_phone(options['phone'])
        owner = find_user_by_phone(phone)
        if not owner:
            owner = User.objects.filter(phone=phone).first()
        if not owner:
            raise CommandError(f'کاربر با شماره {phone} یافت نشد.')

        membership = get_membership(owner)
        if not membership:
            raise CommandError('کاربر عضو آژانس نیست — ابتدا آژانس بسازید یا seed_crm_demo را اجرا کنید.')

        agency = membership.agency
        seat_count = max(2, int(options['seats']))

        with transaction.atomic():
            sub = self._ensure_subscription(owner, agency, seat_count, options['force_sub'])
            mark_agency_onboarding_complete(agency)
            agency.management_status = 'active'
            agency.save(update_fields=['management_status', 'updated_at'])

            advisors = self._ensure_demo_members(owner, agency, sub)
            self._ensure_space_publications(owner, agency, advisors)
            self._ensure_activity_samples(agency, owner, advisors)

        self.stdout.write(self.style.SUCCESS(
            f'OK owner={owner.username} agency={agency.pk} sub={sub.pk} seats={sub.seat_count}',
        ))
        self.stdout.write(f'  advisors: {len(advisors)}')
        self.stdout.write(f'  space_items: {AgencySpaceItem.objects.filter(agency=agency).count()}')

    def _ensure_subscription(self, owner, agency: CRMAgency, seat_count: int, force: bool):
        sub = get_active_subscription_for_owner(owner)
        if sub and not force:
            if not sub.agency_id:
                link_agency_to_subscription(agency, sub)
            self.stdout.write(self.style.WARNING(f'existing active sub={sub.pk}'))
            return sub

        if sub and force:
            sub.status = 'expired'
            sub.save(update_fields=['status', 'updated_at'])

        slug = f'local-agency-{uuid.uuid4().hex[:8]}'
        product = Product.objects.create(
            title='Local Agency Plan',
            slug=slug,
            description='local dev only',
            is_active=True,
        )
        plan = LicensePlan.objects.create(
            product=product,
            name='Local Agency',
            plan_type='monthly',
            price=990_000,
            duration_days=90,
            max_activations=seat_count,
            allow_bulk_purchase=True,
            min_quantity=2,
            max_quantity=20,
            is_active=True,
        )
        order = Order.objects.create(
            user=owner,
            product=product,
            plan=plan,
            quantity=seat_count,
            amount=plan.price * seat_count,
            status='paid',
            paid_at=timezone.now(),
        )
        fulfill_order_after_payment(order)
        sub = provision_subscription_from_paid_order(order)
        if not sub:
            raise CommandError('provision_subscription_from_paid_order ناموفق بود')
        link_agency_to_subscription(agency, sub)
        self.stdout.write(self.style.SUCCESS(f'new sub={sub.pk} licenses={seat_count}'))
        return sub

    def _ensure_demo_members(self, owner, agency: CRMAgency, sub):
        sub = get_subscription_for_agency(agency) or sub
        licenses = list(
            License.objects.filter(agency_subscription=sub, order__status='paid')
            .order_by('sequence', 'pk'),
        )
        free_licenses = [lic for lic in licenses if not lic.assigned_user_id]

        created = []
        for phone, display_name, role in DEMO_ADVISORS:
            phone = normalize_phone(phone)
            user, was_new = User.objects.get_or_create(
                username=phone,
                defaults={'phone': phone, 'first_name': display_name.split()[0], 'last_name': ' '.join(display_name.split()[1:])},
            )
            if was_new:
                user.set_password('local-demo-pass')
                user.save(update_fields=['password'])

            member, mem_new = CRMAgencyMember.objects.get_or_create(
                agency=agency,
                user=user,
                defaults={
                    'role': role,
                    'is_active': True,
                    'data_visibility_consent_at': timezone.now(),
                },
            )
            if not mem_new and role == 'manager' and member.role != 'owner':
                member.role = role
                member.is_active = True
                if not member.data_visibility_consent_at:
                    member.data_visibility_consent_at = timezone.now()
                member.save(update_fields=['role', 'is_active', 'data_visibility_consent_at', 'updated_at'])

            if member.role != 'owner' and free_licenses:
                lic = free_licenses.pop(0)
                try:
                    assign_seat_to_member(owner, lic.pk, user.pk)
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'seat skip {phone}: {exc}'))

            self._ensure_advisor_crm_samples(user, agency)
            created.append(user)

        return created

    def _ensure_advisor_crm_samples(self, user, agency: CRMAgency):
        if CRMProperty.objects.filter(user=user, agency=agency, deleted_at__isnull=True).count() < 2:
            CRMProperty.objects.create(
                user=user,
                agency=agency,
                title=f'فایل نمایشی {user.first_name or user.phone}',
                sale_price=8_500_000_000,
                area=95,
                city='تهران',
                district='منطقه ۵',
                neighborhood='سعادت‌آباد',
                deal_mode='فروش',
            )
            CRMProperty.objects.create(
                user=user,
                agency=agency,
                title=f'اجاره {user.first_name or user.phone} — پونک',
                deposit=300_000_000,
                monthly_rent=18_000_000,
                area=110,
                city='تهران',
                district='منطقه ۵',
                neighborhood='پونک',
                deal_mode='اجاره',
            )
        if Customer.objects.filter(user=user, agency=agency).count() < 2:
            Customer.objects.create(
                user=user,
                agency=agency,
                name=f'مشتری {user.first_name or "نمایشی"}',
                customer_type='خریدار',
                status='در حال پیگیری',
                phone='09121112233',
                gender='male',
            )
            Customer.objects.create(
                user=user,
                agency=agency,
                name=f'مستاجر {user.first_name or "نمایشی"}',
                customer_type='مستاجر',
                status='جدید',
                gender='female',
            )

    def _ensure_space_publications(self, owner, agency: CRMAgency, advisors: list):
        publishers = [owner] + list(advisors)

        for pub in publishers:
            props = CRMProperty.objects.filter(
                user=pub, agency=agency, deleted_at__isnull=True,
            ).order_by('-pk')[:2]
            for prop in props:
                if AgencySpaceItem.objects.filter(
                    agency=agency,
                    property_id=prop.pk,
                    status=AgencySpaceItem.STATUS_ACTIVE,
                ).exists():
                    continue
                try:
                    item = publish_property(
                        pub,
                        prop.pk,
                        visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
                    )
                    emit_agency_activity(
                        agency, pub, EVENT_SPACE_ITEM_PUBLISHED,
                        object_type='property', object_id=prop.pk,
                    )
                    self.stdout.write(f'  published property {prop.pk} -> space {item.pk}')
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'  property publish {prop.pk}: {exc}'))

            customers = Customer.objects.filter(user=pub, agency=agency).order_by('-pk')[:2]
            for idx, cust in enumerate(customers):
                if AgencySpaceItem.objects.filter(
                    agency=agency,
                    customer_id=cust.pk,
                    status=AgencySpaceItem.STATUS_ACTIVE,
                ).exists():
                    continue
                level = (
                    AgencySpaceItem.CONTACT_FULL if idx == 0
                    else AgencySpaceItem.CONTACT_SUMMARY
                )
                try:
                    item = publish_customer(
                        pub,
                        cust.pk,
                        visibility=AgencySpaceItem.VISIBILITY_AGENCY_PUBLIC,
                        contact_share_level=level,
                    )
                    emit_agency_activity(
                        agency, pub, EVENT_SPACE_ITEM_PUBLISHED,
                        object_type='customer', object_id=cust.pk,
                    )
                    self.stdout.write(f'  published contact {cust.pk} -> space {item.pk}')
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f'  contact publish {cust.pk}: {exc}'))

    def _ensure_activity_samples(self, agency, owner, advisors):
        if agency.activity_events.filter(created_at__gte=timezone.now() - timedelta(days=1)).count() >= 5:
            return
        emit_agency_activity(agency, owner, EVENT_PROPERTY_CREATED, object_type='property')
        emit_agency_activity(agency, owner, EVENT_CONTACT_CREATED, object_type='customer')
        for adv in advisors[:2]:
            emit_agency_activity(agency, adv, EVENT_PROPERTY_CREATED, object_type='property')
