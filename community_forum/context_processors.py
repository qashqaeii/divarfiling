"""شمارنده ناوبری تالار."""
from django.core.cache import cache

from community_forum.services.access import user_can_access_forum
from community_forum.services.members import get_or_create_member
from community_forum.services.messages import unread_count


def forum_nav(request):
    if not request.path.startswith('/workspace'):
        return {}
    user = getattr(request, 'user', None)
    if not user_can_access_forum(user):
        return {'forum_nav_enabled': False, 'forum_nav_unread': 0}
    cache_key = f'forum:unread:{user.pk}'
    unread = cache.get(cache_key)
    if unread is None:
        try:
            member = get_or_create_member(user)
            unread = unread_count(member)
        except Exception:
            unread = 0
        cache.set(cache_key, unread, timeout=30)
    return {'forum_nav_enabled': True, 'forum_nav_unread': unread}


def invalidate_forum_unread_cache(user_id: int):
    cache.delete(f'forum:unread:{user_id}')
