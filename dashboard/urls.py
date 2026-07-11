from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('login/google/', views.google_login_start, name='google_login'),
    path('login/google/callback/', views.google_login_callback, name='google_login_callback'),
    path('auth/refresh/', views.refresh_session_view, name='refresh_session'),
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
    path(
        'projects/<slug:project_slug>/documents/<int:document_id>/process/',
        views.process_document,
        name='process_document',
    ),
    path(
        'documents/<int:document_id>/status/',
        views.document_status_partial,
        name='document_status_partial',
    ),
    path('providers/', views.providers, name='providers'),
    path('providers/chat/defaults/', views.update_chat_provider, name='update_chat_provider'),
    path(
        'providers/embeddings/defaults/',
        views.update_embedding_provider,
        name='update_embedding_provider',
    ),
    path('providers/health/', views.check_provider_health, name='check_provider_health'),
    path(
        'providers/projects/<slug:project_slug>/embeddings/sync/',
        views.sync_embeddings,
        name='sync_embeddings',
    ),
    path(
        'providers/projects/<slug:project_slug>/documents/<int:document_id>/embeddings/rebuild/',
        views.rebuild_document_embeddings,
        name='rebuild_document_embeddings',
    ),
    path('workflows/', views.workflows, name='workflows'),
    path(
        'workflows/projects/<slug:project_slug>/new/',
        views.create_workflow,
        name='create_workflow',
    ),
    path(
        'workflows/projects/<slug:project_slug>/<slug:workflow_slug>/delete/',
        views.delete_workflow,
        name='delete_workflow',
    ),
    path(
        'workflows/projects/<slug:project_slug>/<slug:workflow_slug>/steps/new/',
        views.create_workflow_step,
        name='create_workflow_step',
    ),
    path(
        'workflows/projects/<slug:project_slug>/<slug:workflow_slug>/steps/<int:step_id>/delete/',
        views.delete_workflow_step,
        name='delete_workflow_step',
    ),
    path(
        'workflows/projects/<slug:project_slug>/contract-review/setup/',
        views.setup_contract_review,
        name='setup_contract_review',
    ),
    path(
        'workflows/projects/<slug:project_slug>/contract-review/run/',
        views.run_contract_review,
        name='run_contract_review',
    ),
    path(
        'workflows/projects/<slug:project_slug>/job-vacancy/setup/',
        views.setup_job_vacancy,
        name='setup_job_vacancy',
    ),
    path(
        'workflows/projects/<slug:project_slug>/job-vacancy/run/',
        views.run_job_vacancy,
        name='run_job_vacancy',
    ),
    path(
        'workflows/projects/<slug:project_slug>/templates/<slug:template_key>/setup/',
        views.setup_workflow_template,
        name='setup_workflow_template',
    ),
    path(
        'workflows/projects/<slug:project_slug>/templates/<slug:template_key>/run/',
        views.run_workflow_template,
        name='run_workflow_template',
    ),
    path(
        'workflows/projects/<slug:project_slug>/<slug:workflow_slug>/run/',
        views.run_workflow,
        name='run_workflow',
    ),
    path('executions/', views.executions, name='executions'),
    path('executions/<int:run_id>/', views.execution_detail, name='execution_detail'),
    path(
        'executions/<int:run_id>/status/',
        views.execution_status_partial,
        name='execution_status_partial',
    ),
    path('settings/', views.settings_function, name='settings'),
]
