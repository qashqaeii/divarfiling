"""ثبت بازدید روزانه مقالات برای Analytics پنل."""
from __future__ import annotations

from django.db.models import F
from django.utils import timezone

from blog.models import Post, PostViewDaily


def record_post_view(post: Post) -> None:
    """یک بازدید برای مقاله در تاریخ محلی امروز ثبت می‌کند."""
    today = timezone.localdate()
    row, created = PostViewDaily.objects.get_or_create(
        post=post,
        date=today,
        defaults={'views': 1},
    )
    if not created:
        PostViewDaily.objects.filter(pk=row.pk).update(views=F('views') + 1)
