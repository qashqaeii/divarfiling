"""ابطال سبک کش تطبیق — revision per user (بدون aggregate روی کل آگهی‌ها)."""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from workspace.models import CRMProperty, Customer, Dataset, Listing
from workspace.services.crm_matching_index import (
    bump_user_contacts_match_catalog,
    bump_user_crm_properties_match_catalog,
    bump_user_divar_listings_match_catalog,
    bump_agency_crm_properties_match_catalog,
)


def _listing_owner_user_id(listing: Listing) -> int | None:
    uid = getattr(listing, 'user_id', None)
    if uid:
        return int(uid)
    ds = getattr(listing, 'dataset', None)
    if ds is not None and getattr(ds, 'user_id', None):
        return int(ds.user_id)
    if listing.dataset_id:
        return (
            Dataset.objects.filter(pk=listing.dataset_id)
            .values_list('user_id', flat=True)
            .first()
        )
    return None


@receiver(post_save, sender=Listing)
@receiver(post_delete, sender=Listing)
def _listing_match_catalog_signal(sender, instance: Listing, **kwargs) -> None:
    user_id = _listing_owner_user_id(instance)
    if user_id:
        bump_user_divar_listings_match_catalog(user_id)


@receiver(post_save, sender=Dataset)
def _dataset_match_catalog_signal(sender, instance: Dataset, **kwargs) -> None:
    if instance.user_id:
        bump_user_divar_listings_match_catalog(int(instance.user_id))


@receiver(post_save, sender=CRMProperty)
@receiver(post_delete, sender=CRMProperty)
def _crm_property_match_catalog_signal(sender, instance: CRMProperty, **kwargs) -> None:
    if instance.user_id:
        bump_user_crm_properties_match_catalog(int(instance.user_id))
    if instance.agency_id:
        bump_agency_crm_properties_match_catalog(int(instance.agency_id))


@receiver(post_save, sender=Customer)
@receiver(post_delete, sender=Customer)
def _customer_match_catalog_signal(sender, instance: Customer, **kwargs) -> None:
    if instance.user_id:
        bump_user_contacts_match_catalog(int(instance.user_id))
