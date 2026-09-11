"""Test helpers for agency hub tests."""
from datetime import timedelta

from django.utils import timezone

from shop.models import LicensePlan, Product
from workspace.models import AgencySubscription


def ensure_agency_subscription(owner, agency) -> AgencySubscription:
    existing = AgencySubscription.objects.filter(
        owner=owner,
        agency=agency,
        status=AgencySubscription.STATUS_ACTIVE,
        expires_at__gt=timezone.now(),
    ).first()
    if existing:
        return existing
    product = Product.objects.create(
        title='Agency Test',
        slug=f'agency-test-{agency.pk}',
        description='test',
        is_active=True,
    )
    plan = LicensePlan.objects.create(
        product=product,
        name='Agency Test Plan',
        plan_type='monthly',
        price=990_000,
        duration_days=30,
        max_activations=3,
        allow_bulk_purchase=True,
        min_quantity=1,
        max_quantity=10,
        is_active=True,
    )
    return AgencySubscription.objects.create(
        owner=owner,
        agency=agency,
        plan=plan,
        seat_count=3,
        starts_at=timezone.now() - timedelta(days=1),
        expires_at=timezone.now() + timedelta(days=30),
        status=AgencySubscription.STATUS_ACTIVE,
    )
