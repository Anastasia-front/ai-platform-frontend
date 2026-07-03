from django.shortcuts import render

from .services import backend_api

MAIN_ENDPOINTS = [
    {'method': 'GET', 'path': '/health', 'area': 'Health'},
    {'method': 'POST', 'path': '/auth/register', 'area': 'Auth'},
    {'method': 'POST', 'path': '/auth/login', 'area': 'Auth'},
    {'method': 'GET', 'path': '/auth/me', 'area': 'Auth'},
    {'method': 'GET', 'path': '/projects/', 'area': 'Projects'},
    {'method': 'GET', 'path': '/projects/{project_id}', 'area': 'Projects'},
    {'method': 'POST', 'path': '/projects/{project_id}/retrieve', 'area': 'Projects'},
    {'method': 'GET', 'path': '/projects/{project_id}/workflows', 'area': 'Workflows'},
    {'method': 'GET', 'path': '/workflows/{workflow_id}', 'area': 'Workflows'},
    {'method': 'POST', 'path': '/workflows/{workflow_id}/run', 'area': 'Workflows'},
    {'method': 'POST', 'path': '/workflows/{workflow_id}/runs/stream', 'area': 'Workflows'},
    {'method': 'GET', 'path': '/runs/{run_id}', 'area': 'Executions'},
    {'method': 'GET', 'path': '/runs/{run_id}/events', 'area': 'Executions'},
    {'method': 'POST', 'path': '/runs/{run_id}/resume', 'area': 'Executions'},
    {'method': 'GET', 'path': '/projects/{project_id}/documents', 'area': 'Documents'},
    {'method': 'GET', 'path': '/documents/{document_id}/chunks', 'area': 'Documents'},
    {'method': 'POST', 'path': '/documents/{document_id}/process', 'area': 'Documents'},
    {'method': 'POST', 'path': '/documents/{document_id}/embeddings/rebuild', 'area': 'Providers'},
    {'method': 'POST', 'path': '/projects/{project_id}/embeddings/sync', 'area': 'Providers'},
    {'method': 'GET', 'path': '/projects/{project_id}/chats', 'area': 'Chats'},
    {'method': 'GET', 'path': '/chats/{chat_id}', 'area': 'Chats'},
    {'method': 'GET', 'path': '/agent_runs/{agent_run_id}', 'area': 'Agent Runs'},
]


def index(request):
    backend_health = None
    backend_error = None
    projects = []
    projects_error = None

    try:
        backend_health = backend_api.get_health()
    except backend_api.BackendAPIError as exc:
        backend_error = exc.message

    try:
        projects = backend_api.list_projects()
    except backend_api.BackendAPIError as exc:
        projects_error = exc.message

    return render(
        request,
        'dashboard/index.html',
        {
            'backend_api_url': backend_api.BASE_API_URL,
            'backend_health': backend_health,
            'backend_error': backend_error,
            'projects': projects,
            'projects_error': projects_error,
        },
    )


def project_detail(request, project_id):
    project = None
    project_error = None

    try:
        project = backend_api.get_project(project_id)
    except backend_api.BackendAPIError as exc:
        project_error = exc.message

    return render(
        request,
        'dashboard/project_detail.html',
        {
            'project': project,
            'project_error': project_error,
            'backend_api_url': backend_api.BASE_API_URL,
        },
    )


def providers(request):
    return render(
        request,
        'dashboard/providers.html',
        {
            'endpoints': _endpoints_for('Providers'),
            'backend_api_url': backend_api.BASE_API_URL,
        },
    )


def workflows(request):
    return render(
        request,
        'dashboard/workflows.html',
        {
            'endpoints': _endpoints_for('Workflows'),
            'backend_api_url': backend_api.BASE_API_URL,
        },
    )


def executions(request):
    return render(
        request,
        'dashboard/executions.html',
        {
            'endpoints': _endpoints_for('Executions'),
            'backend_api_url': backend_api.BASE_API_URL,
        },
    )


def settings(request):
    return render(
        request,
        'dashboard/settings.html',
        {
            'backend_api_url': backend_api.BASE_API_URL,
            'endpoints': MAIN_ENDPOINTS,
        },
    )


def _endpoints_for(area):
    return [endpoint for endpoint in MAIN_ENDPOINTS if endpoint['area'] == area]
