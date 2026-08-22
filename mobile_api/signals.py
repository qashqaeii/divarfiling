"""سیگنال یادآور → زمان‌بندی محلی اندروید."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from workspace.models import Reminder


@receiver(post_save, sender=Reminder)
def reminder_saved_sync_mobile(sender, instance: Reminder, **kwargs):
    from mobile_api.services.reminder_push_sync import sync_reminder_local_schedule

    sync_reminder_local_schedule(instance)


@receiver(post_delete, sender=Reminder)
def reminder_deleted_sync_mobile(sender, instance: Reminder, **kwargs):
    from mobile_api.services.reminder_push_sync import cancel_reminder_local_schedule

    if instance.user_id:
        cancel_reminder_local_schedule(instance.user, instance.pk)
