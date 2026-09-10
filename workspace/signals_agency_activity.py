"""Signal hooks برای AgencyActivityEvent — business events only."""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from workspace.models import (
    CRMDeal,
    CRMDealFollowUp,
    CRMProperty,
    Customer,
    CustomerActivity,
    Dataset,
    PropertyVisit,
)
from workspace.services.agency_activity import (
    EVENT_CALL,
    EVENT_CONTACT_CREATED,
    EVENT_DATASET_CREATED,
    EVENT_DEAL_CREATED,
    EVENT_DEAL_STAGE_CHANGED,
    EVENT_FOLLOW_UP,
    EVENT_PROPERTY_CREATED,
    EVENT_VISIT,
    emit_agency_activity,
    emit_for_user_record,
)

_DEAL_STAGE_CACHE: dict[int, str] = {}


@receiver(pre_save, sender=CRMDeal)
def _cache_deal_stage(sender, instance, **kwargs):
    if instance.pk:
        try:
            old = CRMDeal.objects.filter(pk=instance.pk).values_list('stage', flat=True).first()
            if old:
                _DEAL_STAGE_CACHE[instance.pk] = old
        except Exception:
            pass


@receiver(post_save, sender=Customer)
def _customer_created(sender, instance, created, **kwargs):
    if not created or not instance.agency_id:
        return
    emit_agency_activity(
        instance.agency, instance.user, EVENT_CONTACT_CREATED,
        object_type='customer', object_id=instance.pk,
        metadata={'name': instance.name[:80]},
    )


@receiver(post_save, sender=CRMProperty)
def _property_created(sender, instance, created, **kwargs):
    if not created or not instance.agency_id:
        return
    emit_agency_activity(
        instance.agency, instance.user, EVENT_PROPERTY_CREATED,
        object_type='property', object_id=instance.pk,
        metadata={'title': instance.title[:80]},
    )


@receiver(post_save, sender=Dataset)
def _dataset_created(sender, instance, created, **kwargs):
    if not created:
        return
    emit_for_user_record(
        instance.user, EVENT_DATASET_CREATED,
        object_type='dataset', object_id=None,
        metadata={'dataset_id': str(instance.pk), 'name': instance.name[:80]},
    )


@receiver(post_save, sender=CRMDeal)
def _deal_saved(sender, instance, created, **kwargs):
    if not instance.agency_id:
        return
    if created:
        emit_agency_activity(
            instance.agency, instance.user, EVENT_DEAL_CREATED,
            object_type='deal', object_id=instance.pk,
            metadata={'title': instance.title[:80]},
        )
        return
    old_stage = _DEAL_STAGE_CACHE.pop(instance.pk, None)
    if old_stage and old_stage != instance.stage:
        emit_agency_activity(
            instance.agency, instance.user, EVENT_DEAL_STAGE_CHANGED,
            object_type='deal', object_id=instance.pk,
            metadata={'from': old_stage, 'to': instance.stage},
        )


@receiver(post_save, sender=CustomerActivity)
def _customer_activity(sender, instance, created, **kwargs):
    if not created:
        return
    customer = instance.customer
    if not customer or not customer.agency_id:
        return
    atype = (instance.activity_type or '').strip()
    if atype in ('تماس', 'call', 'Call'):
        event = EVENT_CALL
    else:
        event = EVENT_FOLLOW_UP
    emit_agency_activity(
        customer.agency, customer.user, event,
        object_type='customer_activity', object_id=instance.pk,
        metadata={'activity_type': atype, 'customer_id': customer.pk},
    )


@receiver(post_save, sender=PropertyVisit)
def _property_visit(sender, instance, created, **kwargs):
    if not created:
        return
    emit_for_user_record(
        instance.user, EVENT_VISIT,
        object_type='property_visit', object_id=instance.pk,
        metadata={'customer_id': instance.customer_id},
    )


@receiver(post_save, sender=CRMDealFollowUp)
def _deal_followup(sender, instance, created, **kwargs):
    if not created:
        return
    deal = instance.deal
    if not deal or not deal.agency_id:
        return
    actor = instance.user or deal.user
    emit_agency_activity(
        deal.agency, actor, EVENT_FOLLOW_UP,
        object_type='deal_followup', object_id=instance.pk,
        metadata={'deal_id': deal.pk, 'type': instance.follow_up_type},
    )
