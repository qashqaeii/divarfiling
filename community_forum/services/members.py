"""عضویت تالار."""
from django.db import transaction

from community_forum.models import ForumMember
from community_forum.services.identity import validate_display_name


def get_or_create_member(user) -> ForumMember:
    member, _ = ForumMember.objects.get_or_create(user=user)
    return member


@transaction.atomic
def update_display_name(member: ForumMember, raw_name: str) -> ForumMember:
    name, err = validate_display_name(raw_name)
    if err:
        from django.core.exceptions import ValidationError

        raise ValidationError(err)
    member.display_name = name
    member.display_name_approved = True
    member.save(update_fields=['display_name', 'display_name_approved', 'updated_at'])
    return member
