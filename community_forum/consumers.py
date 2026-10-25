"""WebSocket تالار گفتگو."""
import json

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from community_forum.services.access import user_can_access_forum
from community_forum.services.realtime import GROUP_NAME


class ForumConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if not isinstance(user, AnonymousUser) and user_can_access_forum(user):
            self.member_ok = True
        else:
            self.member_ok = False
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connected'})

    async def disconnect(self, close_code):
        if getattr(self, 'member_ok', False):
            await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get('type') == 'ping':
            await self.send_json({'type': 'pong'})

    async def forum_event(self, event):
        await self.send(text_data=json.dumps({
            'type': event.get('event'),
            'payload': event.get('payload'),
        }, ensure_ascii=False))
