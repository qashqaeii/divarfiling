"""گردش‌کار پیشنهاد قابلیت، رای، follow و باگ."""
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from product_hub.models import (
    FeatureFollow,
    FeatureRequest,
    FeatureRequestStatusLog,
    FeatureVote,
)
from product_hub.services import notifications as notif_svc

# مجاز: from -> {to, ...}
REQUEST_TRANSITIONS = {
    'submitted': {'reviewing', 'rejected'},
    'reviewing': {'approved', 'rejected', 'submitted'},
    'approved': {'in_development', 'rejected', 'reviewing'},
    'in_development': {'completed', 'approved', 'rejected'},
    'completed': set(),
    'rejected': {'reviewing', 'submitted'},
}

BUG_TRANSITIONS = {
    'reported': {'reviewing', 'fixing', 'resolved'},
    'reviewing': {'fixing', 'resolved', 'reported'},
    'fixing': {'resolved', 'reviewing'},
    'resolved': {'fixing'},
}


class WorkflowError(Exception):
    pass


@transaction.atomic
def change_request_status(request_obj, *, to_status, actor, note='', released_in=None,
                          release_note='', linked_feature=None):
    from_status = request_obj.status
    if to_status == from_status:
        return request_obj

    allowed = REQUEST_TRANSITIONS.get(from_status, set())
    if to_status not in allowed and not getattr(actor, 'is_superuser', False):
        # staff می‌تواند هر انتقال منطقی را اعمال کند؛ فقط completed نیاز به نسخه دارد
        pass

    if to_status == 'completed':
        if not released_in and not request_obj.released_in_id:
            raise WorkflowError('برای تکمیل پیشنهاد باید نسخه انتشار مشخص شود.')
        request_obj.released_in = released_in or request_obj.released_in
        request_obj.shipped_at = timezone.now()
        if release_note:
            request_obj.release_note = release_note
        if not request_obj.release_note:
            raise WorkflowError('برای تکمیل پیشنهاد توضیح انتشار الزامی است.')

    if note:
        request_obj.staff_note = note
    if linked_feature is not None:
        request_obj.linked_feature = linked_feature

    request_obj.status = to_status
    request_obj.save()

    FeatureRequestStatusLog.objects.create(
        request=request_obj,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        note=note or release_note,
    )
    notif_svc.notify_request_status(request_obj, to_status)
    return request_obj


@transaction.atomic
def change_bug_status(bug, *, to_status, actor, note='', resolution_note=''):
    from_status = bug.status
    if to_status == from_status:
        return bug

    if to_status == 'resolved':
        if not resolution_note and not bug.resolution_note:
            raise WorkflowError('برای رفع مشکل توضیح رفع الزامی است.')
        if resolution_note:
            bug.resolution_note = resolution_note
        bug.resolved_at = timezone.now()
        bug.resolved_by = actor

    if note:
        bug.staff_note = note
    bug.status = to_status
    bug.save()

    if to_status == 'resolved':
        notif_svc.notify_bug_resolved(bug)
    return bug


@transaction.atomic
def toggle_vote(request_obj, user):
    existing = FeatureVote.objects.filter(request=request_obj, user=user).first()
    if existing:
        existing.delete()
        FeatureRequest.objects.filter(pk=request_obj.pk, votes_count__gt=0).update(
            votes_count=F('votes_count') - 1,
        )
        voted = False
    else:
        FeatureVote.objects.create(request=request_obj, user=user)
        FeatureRequest.objects.filter(pk=request_obj.pk).update(
            votes_count=F('votes_count') + 1,
        )
        voted = True
    request_obj.refresh_from_db(fields=['votes_count'])
    return voted, request_obj.votes_count


@transaction.atomic
def toggle_follow(request_obj, user):
    existing = FeatureFollow.objects.filter(request=request_obj, user=user).first()
    if existing:
        existing.delete()
        FeatureRequest.objects.filter(pk=request_obj.pk, follows_count__gt=0).update(
            follows_count=F('follows_count') - 1,
        )
        following = False
    else:
        FeatureFollow.objects.create(request=request_obj, user=user)
        FeatureRequest.objects.filter(pk=request_obj.pk).update(
            follows_count=F('follows_count') + 1,
        )
        following = True
    request_obj.refresh_from_db(fields=['follows_count'])
    return following, request_obj.follows_count
