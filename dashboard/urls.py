from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('projects/', views.projects, name='projects'),
    path('projects/new/', views.new_project, name='new_project'),
    path('projects/<slug:project_slug>/', views.project_detail, name='project_detail'),
    path('projects/<slug:project_slug>/delete/', views.delete_project, name='delete_project'),
    path('projects/<slug:project_slug>/chats/new/', views.new_chat, name='new_chat'),
    path(
        'projects/<slug:project_slug>/chats/<slug:chat_slug>/',
        views.chat_detail,
        name='chat_detail',
    ),
    path(
        'projects/<slug:project_slug>/chats/<slug:chat_slug>/delete/',
        views.delete_chat,
        name='delete_chat',
    ),
    path(
        'projects/<slug:project_slug>/chats/<slug:chat_slug>/messages/send/',
        views.send_chat_message,
        name='send_chat_message',
    ),
    path(
        'projects/<slug:project_slug>/documents/upload/',
        views.upload_document,
        name='upload_document',
    ),
    path(
        'projects/<slug:project_slug>/documents/<int:document_id>/delete/',
        views.delete_document,
        name='delete_document',
    ),
    path('providers/', views.providers, name='providers'),
    path('workflows/', views.workflows, name='workflows'),
    path('executions/', views.executions, name='executions'),
    path('settings/', views.settings, name='settings'),
]
