from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('projects/<int:project_id>/', views.project_detail, name='project_detail'),
    path('providers/', views.providers, name='providers'),
    path('workflows/', views.workflows, name='workflows'),
    path('executions/', views.executions, name='executions'),
    path('settings/', views.settings, name='settings'),
]
