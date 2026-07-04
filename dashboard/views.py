from functools import wraps

from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .services import backend_api

MAIN_ENDPOINTS = [
    {'method': 'GET', 'path': '/health', 'area': 'Health'},
    {'method': 'POST', 'path': '/auth/register', 'area': 'Auth'},
    {'method': 'POST', 'path': '/auth/login', 'area': 'Auth'},
    {'method': 'GET', 'path': '/auth/me', 'area': 'Auth'},
    {'method': 'GET', 'path': '/projects/', 'area': 'Projects'},
    {'method': 'POST', 'path': '/projects/', 'area': 'Projects'},
    {'method': 'GET', 'path': '/projects/{project_id}', 'area': 'Projects'},
    {'method': 'DELETE', 'path': '/projects/{project_id}', 'area': 'Projects'},
    {'method': 'POST', 'path': '/projects/{project_id}/retrieve', 'area': 'Projects'},
    {'method': 'GET', 'path': '/projects/{project_id}/chats', 'area': 'Chats'},
    {'method': 'POST', 'path': '/projects/{project_id}/chats', 'area': 'Chats'},
    {'method': 'GET', 'path': '/chats/{chat_id}', 'area': 'Chats'},
    {'method': 'DELETE', 'path': '/chats/{chat_id}', 'area': 'Chats'},
    {'method': 'GET', 'path': '/chats/{chat_id}/messages', 'area': 'Messages'},
    {'method': 'POST', 'path': '/chats/{chat_id}/messages', 'area': 'Messages'},
    {'method': 'GET', 'path': '/projects/{project_id}/documents', 'area': 'Documents'},
    {'method': 'POST', 'path': '/projects/{project_id}/documents', 'area': 'Documents'},
    {'method': 'DELETE', 'path': '/documents/{document_id}', 'area': 'Documents'},
    {'method': 'GET', 'path': '/documents/{document_id}/chunks', 'area': 'Documents'},
    {'method': 'POST', 'path': '/documents/{document_id}/process', 'area': 'Documents'},
    {'method': 'GET', 'path': '/projects/{project_id}/workflows', 'area': 'Workflows'},
    {'method': 'GET', 'path': '/runs/{run_id}/events', 'area': 'Executions'},
]

AGENT_MODES = [
    {'value': 'assistant', 'label': 'Assistant'},
    {'value': 'coding', 'label': 'Coding'},
    {'value': 'research', 'label': 'Research'},
]


def session_token(request):
    return request.session.get('access_token')


def auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not session_token(request):
            return redirect(f"{reverse('dashboard:login')}?next={request.path}")
        return view_func(request, *args, **kwargs)

    return wrapped


def index(request):
    if session_token(request):
        return redirect('dashboard:projects')
    return redirect('dashboard:login')


def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        try:
            token_payload = backend_api.login(email, password)
            request.session['access_token'] = token_payload['access_token']
            request.session['token_type'] = token_payload.get('token_type', 'bearer')
            try:
                request.session['user'] = backend_api.get_current_user(
                    request.session['access_token']
                )
            except backend_api.BackendAPIError:
                request.session['user'] = {'email': email}
            return redirect(request.GET.get('next') or 'dashboard:projects')
        except backend_api.BackendAPIError as exc:
            django_messages.error(request, exc.message)

    return render_auth(request, 'dashboard/auth/login.html')


def register_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        try:
            backend_api.register(email, password)
            django_messages.success(request, 'Account created. You can log in now.')
            return redirect('dashboard:login')
        except backend_api.BackendAPIError as exc:
            django_messages.error(request, exc.message)

    return render_auth(request, 'dashboard/auth/register.html')


def logout_view(request):
    request.session.flush()
    return redirect('dashboard:login')


@auth_required
def projects(request):
    context = app_context(request)
    return render(request, 'dashboard/projects/list.html', context)


@auth_required
def new_project(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()

        if not name:
            django_messages.error(request, 'Project name is required.')
        else:
            try:
                project = backend_api.create_project(session_token(request), name, description)
                return redirect(
                    'dashboard:project_detail',
                    project_slug=resource_slug(project, 'name'),
                )
            except backend_api.BackendAPIError as exc:
                handle_api_error(request, exc)
                django_messages.error(request, exc.message)

    return render(request, 'dashboard/projects/new.html', app_context(request))


@auth_required
def project_detail(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    context = app_context(request, active_project_slug=project_slug)

    if project_error:
        context['page_error'] = project_error
        return render(request, 'dashboard/chat/workspace.html', context)

    project = with_slug(project, 'name')
    context['active_project'] = project

    try:
        context['chats'] = with_slugs(
            backend_api.list_project_chats(token, project['id']),
            'title',
        )
        context['documents'] = backend_api.list_project_documents(token, project['id'])
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context['page_error'] = exc.message

    return render(request, 'dashboard/chat/workspace.html', context)


@auth_required
@require_POST
def delete_project(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect('dashboard:projects')

    try:
        backend_api.delete_project(token, project['id'])
        django_messages.success(request, 'Project deleted.')
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect('dashboard:projects')


@auth_required
@require_POST
def new_chat(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect('dashboard:projects')

    title = request.POST.get('title', '').strip() or 'New chat'
    agent_name = request.POST.get('agent_name', 'assistant')
    if agent_name not in {mode['value'] for mode in AGENT_MODES}:
        agent_name = 'assistant'

    try:
        chat = backend_api.create_chat(
            token,
            project['id'],
            title,
            agent_name=agent_name,
        )
        return redirect(
            'dashboard:chat_detail',
            project_slug=resource_slug(project, 'name'),
            chat_slug=resource_slug(chat, 'title'),
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)
        return redirect('dashboard:project_detail', project_slug=resource_slug(project, 'name'))


@auth_required
def chat_detail(request, project_slug, chat_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    context = app_context(
        request,
        active_project_slug=project_slug,
        active_chat_slug=chat_slug,
    )

    if project_error:
        context['page_error'] = project_error
        return render(request, 'dashboard/chat/workspace.html', context)

    project = with_slug(project, 'name')
    context['active_project'] = project

    chat, chat_error = resolve_chat(token, project['id'], chat_slug)
    if chat_error:
        context['page_error'] = chat_error
        return render(request, 'dashboard/chat/workspace.html', context)

    chat = with_slug(chat, 'title')

    try:
        context['active_chat'] = chat
        context['chats'] = with_slugs(
            backend_api.list_project_chats(token, project['id']),
            'title',
        )
        context['chat_messages'] = backend_api.list_messages(token, chat['id'])
        context['documents'] = backend_api.list_project_documents(token, project['id'])
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context['page_error'] = exc.message

    return render(request, 'dashboard/chat/workspace.html', context)


@auth_required
@require_POST
def delete_chat(request, project_slug, chat_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect('dashboard:projects')

    chat, chat_error = resolve_chat(token, project['id'], chat_slug)
    if chat_error:
        django_messages.error(request, chat_error)
        return redirect('dashboard:project_detail', project_slug=resource_slug(project, 'name'))

    try:
        backend_api.delete_chat(token, chat['id'])
        django_messages.success(request, 'Chat deleted.')
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect('dashboard:project_detail', project_slug=resource_slug(project, 'name'))


@auth_required
@require_POST
def send_chat_message(request, project_slug, chat_slug):
    content = request.POST.get('content', '').strip()
    token = session_token(request)
    chat_messages = []
    error = None

    project, project_error = resolve_project(token, project_slug)
    chat = None

    if project_error:
        error = project_error
    else:
        chat, chat_error = resolve_chat(token, project['id'], chat_slug)
        if chat_error:
            error = chat_error

    if not content and error is None:
        error = 'Message cannot be empty.'
    elif error is None:
        try:
            backend_api.send_message(token, chat['id'], content)
            chat_messages = backend_api.list_messages(token, chat['id'])
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            error = exc.message

    if request.headers.get('HX-Request'):
        return render(
            request,
            'dashboard/chat/_messages.html',
            {'chat_messages': chat_messages, 'message_error': error},
        )

    if error:
        django_messages.error(request, error)
    return redirect('dashboard:chat_detail', project_slug=project_slug, chat_slug=chat_slug)


@auth_required
@require_POST
def upload_document(request, project_slug):
    token = session_token(request)
    next_url = safe_next_url(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or 'dashboard:projects')

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        django_messages.error(request, 'Choose a document to upload.')
    else:
        try:
            backend_api.upload_document(token, project['id'], uploaded_file)
            django_messages.success(request, 'Document uploaded.')
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            django_messages.error(request, exc.message)

    return redirect(next_url or reverse('dashboard:project_detail', kwargs={'project_slug': resource_slug(project, 'name')}))


@auth_required
@require_POST
def delete_document(request, project_slug, document_id):
    next_url = safe_next_url(request)
    project, project_error = resolve_project(session_token(request), project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or 'dashboard:projects')

    try:
        backend_api.delete_document(session_token(request), document_id)
        django_messages.success(request, 'Document deleted.')
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(next_url or reverse('dashboard:project_detail', kwargs={'project_slug': resource_slug(project, 'name')}))


@auth_required
def providers(request):
    return render(
        request,
        'dashboard/utility/providers.html',
        app_context(request, endpoints=_endpoints_for('Providers')),
    )


@auth_required
def workflows(request):
    return render(
        request,
        'dashboard/utility/workflows.html',
        app_context(request, endpoints=_endpoints_for('Workflows')),
    )


@auth_required
def executions(request):
    return render(
        request,
        'dashboard/utility/executions.html',
        app_context(request, endpoints=_endpoints_for('Executions')),
    )


@auth_required
def settings(request):
    return render(
        request,
        'dashboard/utility/settings.html',
        app_context(request, endpoints=MAIN_ENDPOINTS),
    )


def app_context(request, active_project_slug=None, active_chat_slug=None, endpoints=None):
    token = session_token(request)
    projects_payload = []
    projects_error = None

    if token:
        try:
            projects_payload = with_slugs(backend_api.list_projects(token), 'name')
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            projects_error = exc.message

    return {
        'backend_api_url': backend_api.BASE_API_URL,
        'current_user': request.session.get('user'),
        'projects': projects_payload,
        'projects_error': projects_error,
        'active_project_slug': active_project_slug,
        'active_chat_slug': active_chat_slug,
        'endpoints': endpoints or [],
        'agent_modes': AGENT_MODES,
    }


def render_auth(request, template_name):
    return render(
        request,
        template_name,
        {'backend_api_url': backend_api.BASE_API_URL},
    )


def handle_api_error(request, exc):
    if exc.status_code == 401:
        request.session.pop('access_token', None)
        django_messages.error(request, 'Your session expired. Please log in again.')


def _endpoints_for(area):
    return [endpoint for endpoint in MAIN_ENDPOINTS if endpoint['area'] == area]


def safe_next_url(request):
    next_url = request.POST.get('next', '')
    if next_url.startswith('/'):
        return next_url
    return ''


def resource_slug(resource, field):
    return slugify(resource.get(field, '')) or 'untitled'


def with_slug(resource, field):
    resource = dict(resource)
    resource['slug'] = resource_slug(resource, field)
    return resource


def with_slugs(resources, field):
    return [with_slug(resource, field) for resource in resources]


def resolve_project(token, project_slug):
    try:
        projects_payload = backend_api.list_projects(token)
    except backend_api.BackendAPIError as exc:
        return None, exc.message

    for project in projects_payload:
        if resource_slug(project, 'name') == project_slug:
            return project, None

    return None, 'Project not found.'


def resolve_chat(token, project_id, chat_slug):
    try:
        chats_payload = backend_api.list_project_chats(token, project_id)
    except backend_api.BackendAPIError as exc:
        return None, exc.message

    for chat in chats_payload:
        if resource_slug(chat, 'title') == chat_slug:
            return chat, None

    return None, 'Chat not found.'
