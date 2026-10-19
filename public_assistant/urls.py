from django.urls import path

from public_assistant import views

app_name = 'public_assistant'

urlpatterns = [
    path('config/', views.config_view, name='config'),
    path('chat/', views.chat_view, name='chat'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('reset/', views.reset_session_view, name='reset'),
]
