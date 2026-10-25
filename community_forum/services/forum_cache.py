"""کش مشترک تالار — ban، قفل purge و موارد چند Worker."""
from django.core.cache import caches

SHARED_ALIAS = 'forum_shared'


def shared_cache():
    return caches[SHARED_ALIAS]
