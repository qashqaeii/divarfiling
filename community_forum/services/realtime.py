"""انتشار رویداد WebSocket."""
import logging

logger = logging.getLogger(__name__)

GROUP_NAME = 'forum_public'


def member_group_name(member_id: int) -> str:
    return f'forum_member_{member_id}'


def broadcast_event(event_type: str, payload: dict) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            GROUP_NAME,
            {
                'type': 'forum.event',
                'event': event_type,
                'payload': payload,
            },
        )
    except Exception:
        logger.exception('forum broadcast failed event=%s', event_type)


def notify_member(member_id: int, event_type: str, payload: dict) -> None:
    """رویداد شخصی — مثلاً قطع اتصال پس از ban."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            member_group_name(member_id),
            {
                'type': 'forum.event',
                'event': event_type,
                'payload': payload,
            },
        )
    except Exception:
        logger.exception('forum member notify failed member=%s', member_id)
