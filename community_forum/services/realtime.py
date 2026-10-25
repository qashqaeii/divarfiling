"""انتشار رویداد WebSocket."""
GROUP_NAME = 'forum_public'


def broadcast_event(event_type: str, payload: dict) -> None:
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        GROUP_NAME,
        {
            'type': 'forum.event',
            'event': event_type,
            'payload': payload,
        },
    )
