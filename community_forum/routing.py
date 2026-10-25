from django.urls import path

from community_forum.consumers import ForumConsumer

websocket_urlpatterns = [
    path('ws/forum/', ForumConsumer.as_asgi()),
]
