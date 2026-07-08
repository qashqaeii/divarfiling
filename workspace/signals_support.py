"""سیگنال‌های تیکت پشتیبانی."""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


@receiver(post_save, sender='workspace.TicketMessage')
def sync_ticket_on_message(sender, instance, created, **kwargs):
    """همگام‌سازی وضعیت تیکت پس از ثبت پیام (مثلاً از Django Admin)."""
    if not created or instance.is_internal:
        return
    ticket = instance.ticket
    ticket.last_message_at = timezone.now()
    if instance.is_staff_reply:
        ticket.user_has_unread = True
        ticket.staff_has_unread = False
        if ticket.status in ('open', 'in_review'):
            ticket.status = 'answered'
    else:
        ticket.staff_has_unread = True
        ticket.user_has_unread = False
    ticket.save(update_fields=[
        'last_message_at', 'user_has_unread', 'staff_has_unread', 'status', 'updated_at',
    ])
