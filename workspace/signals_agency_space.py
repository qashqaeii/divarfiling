"""Signals Agency Space — حذف/soft-delete منبع."""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from workspace.models import CRMProperty, Customer
from workspace.services.agency_space_lifecycle import (
    archive_publications_for_customer,
    archive_publications_for_property,
)


@receiver(post_save, sender=CRMProperty)
def archive_space_on_property_soft_delete(sender, instance, **kwargs):
    if instance.deleted_at:
        archive_publications_for_property(instance)


@receiver(pre_delete, sender=CRMProperty)
def archive_space_on_property_delete(sender, instance, **kwargs):
    archive_publications_for_property(instance)


@receiver(pre_delete, sender=Customer)
def archive_space_on_customer_delete(sender, instance, **kwargs):
    archive_publications_for_customer(instance)
