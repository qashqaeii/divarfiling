"""WebSocket تالار گفتگو."""
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from community_forum.services.access import user_can_access_forum
from community_forum.services.members import get_or_create_member
from community_forum.services.moderation import member_can_read
from community_forum.services.realtime import GROUP_NAME, member_group_name


@database_sync_to_async
def _resolve_member(user):
    if not user_can_access_forum(user):
        return None
    member = get_or_create_member(user)
    if not member_can_read(member):
        return None
    return member


@database_sync_to_async
def _still_can_read(member_id: int) -> bool:
    from community_forum.models import ForumMember

    member = ForumMember.objects.filter(pk=member_id).first()
    if not member:
        return False
    return member_can_read(member)


class ForumConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get('user')
        if isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4403)
            return
        member = await _resolve_member(user)
        if not member:
            await self.close(code=4403)
            return
        self.member_ok = True
        self.member_id = member.id
        self.public_id = str(member.public_id)
        await self.channel_layer.group_add(GROUP_NAME, self.channel_name)
        await self.channel_layer.group_add(member_group_name(member.id), self.channel_name)
        await self.accept()
        await self.send_json({'type': 'connected', 'sender_public_id': self.public_id})

    async def disconnect(self, close_code):
        if getattr(self, 'member_ok', False):
            await self.channel_layer.group_discard(GROUP_NAME, self.channel_name)
            await self.channel_layer.group_discard(
                member_group_name(self.member_id),
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        if content.get('type') == 'ping':
            if not await _still_can_read(self.member_id):
                await self.close(code=4403)
                return
            await self.send_json({'type': 'pong'})

    async def forum_event(self, event):
        if event.get('event') == 'session.revoked':
            if event.get('payload', {}).get('reason') == 'ban':
                await self.close(code=4403)
            return
        if not await _still_can_read(self.member_id):
            await self.close(code=4403)
            return
        await self.send(
            text_data=json.dumps(
                {
                    'type': event.get('event'),
                    'payload': event.get('payload'),
                },
                ensure_ascii=False,
            ),
        )
