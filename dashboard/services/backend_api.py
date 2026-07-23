import os
from urllib.parse import urlencode

import requests
from django.conf import settings

BASE_API_URL = os.getenv(
    'BASE_API_URL',
    getattr(settings, 'BASE_API_URL', 'http://localhost:8000'),
).rstrip('/')
API_DOCS_URL = os.getenv(
    'API_DOCS_URL',
    getattr(settings, 'API_DOCS_URL', f'{BASE_API_URL}/docs'),
).rstrip('/')
REQUEST_TIMEOUT = 30
WORKFLOW_TIMEOUT = 180
REQUEST_TIMEOUT = int(getattr(settings, 'BACKEND_REQUEST_TIMEOUT', REQUEST_TIMEOUT))
WORKFLOW_TIMEOUT = int(getattr(settings, 'BACKEND_WORKFLOW_TIMEOUT', WORKFLOW_TIMEOUT))


class BackendAPIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _headers(token=None):
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    return headers


def _request(method, path, token=None, timeout=None, **kwargs):
    url = f'{BASE_API_URL}{path}'
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(token),
            timeout=timeout or REQUEST_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        detail = _extract_error_detail(exc.response)
        raise BackendAPIError(
            detail or f'Backend request failed with status {status_code}.',
            status_code=status_code,
        ) from exc
    except requests.Timeout as exc:
        raise BackendAPIError(
            'The backend is still taking too long to finish this request. '
            'Try again, or increase BACKEND_WORKFLOW_TIMEOUT for long workflow runs.'
        ) from exc
    except requests.RequestException as exc:
        raise BackendAPIError(str(exc)) from exc

    if response.status_code == 204:
        return None

    return response.json()


def _extract_error_detail(response):
    if response is None:
        return ''

    try:
        payload = response.json()
    except ValueError:
        return response.text

    detail = payload.get('detail')
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        return '; '.join(str(item.get('msg', item)) for item in detail)

    return ''


def login(email, password):
    return _request(
        'POST',
        '/auth/login',
        data={'username': email, 'password': password},
    )


def register(email, password):
    return _request(
        'POST',
        '/auth/register',
        json={'email': email, 'password': password},
    )


def google_login(credential):
    return _request(
        'POST',
        '/auth/google',
        json={'credential': credential},
    )


def refresh_token(refresh_token_value):
    return _request(
        'POST',
        '/auth/refresh',
        json={'refresh_token': refresh_token_value},
    )


def get_current_user(token):
    return _request('GET', '/auth/me', token=token)


def get_health():
    return _request('GET', '/health')


def list_projects(token):
    return _request('GET', '/projects/', token=token)


def create_project(token, name, description=''):
    return _request(
        'POST',
        '/projects/',
        token=token,
        json={'name': name, 'description': description or None},
    )


def get_project(token, project_id):
    return _request('GET', f'/projects/{project_id}', token=token)


def update_project(token, project_id, name):
    return _request(
        'PATCH',
        f'/projects/{project_id}',
        token=token,
        json={'name': name},
    )


def delete_project(token, project_id):
    return _request('DELETE', f'/projects/{project_id}', token=token)


def list_project_chats(token, project_id):
    return _request('GET', f'/projects/{project_id}/chats', token=token)


def create_chat(token, project_id, title, agent_name='assistant'):
    return _request(
        'POST',
        f'/projects/{project_id}/chats',
        token=token,
        json={'title': title, 'agent_name': agent_name},
    )


def get_chat(token, chat_id):
    return _request('GET', f'/chats/{chat_id}', token=token)


def update_chat(token, chat_id, title):
    return _request(
        'PATCH',
        f'/chats/{chat_id}',
        token=token,
        json={'title': title},
    )


def delete_chat(token, chat_id):
    return _request('DELETE', f'/chats/{chat_id}', token=token)


def list_messages(token, chat_id):
    return _request('GET', f'/chats/{chat_id}/messages', token=token)


def get_message(token, chat_id, message_id):
    messages = list_messages(token, chat_id)
    for message in messages:
        if str(message.get('id')) == str(message_id):
            return message
    raise BackendAPIError('Message was not found.', status_code=404)


def send_message(token, chat_id, content, agent_name=None):
    payload = {'content': content}
    if agent_name:
        payload['agent_name'] = agent_name

    return _request(
        'POST',
        f'/chats/{chat_id}/messages',
        token=token,
        json=payload,
    )


def stream_message(token, chat_id, content, agent_name=None):
    payload = {'content': content}
    if agent_name:
        payload['agent_name'] = agent_name

    try:
        response = requests.post(
            f'{BASE_API_URL}/chats/{chat_id}/messages/stream',
            headers=_headers(token),
            json=payload,
            timeout=(REQUEST_TIMEOUT, WORKFLOW_TIMEOUT),
            stream=True,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        detail = _extract_error_detail(exc.response)
        raise BackendAPIError(
            detail or f'Backend request failed with status {status_code}.',
            status_code=status_code,
        ) from exc
    except requests.Timeout as exc:
        raise BackendAPIError('The backend is still taking too long to stream this message.') from exc
    except requests.RequestException as exc:
        raise BackendAPIError(str(exc)) from exc

    return response


def list_project_documents(token, project_id):
    return _request('GET', f'/projects/{project_id}/documents', token=token)


def upload_document(token, project_id, uploaded_file):
    files = {
        'file': (
            uploaded_file.name,
            uploaded_file,
            getattr(uploaded_file, 'content_type', 'application/octet-stream'),
        )
    }
    return _request(
        'POST',
        f'/projects/{project_id}/documents',
        token=token,
        files=files,
    )


def delete_document(token, document_id):
    return _request('DELETE', f'/documents/{document_id}', token=token)


def process_document(token, document_id):
    # Backend enqueues a Celery task and returns 202 immediately.
    return _request('POST', f'/documents/{document_id}/process', token=token)


def cancel_document_processing(token, document_id):
    return _request('POST', f'/documents/{document_id}/process/cancel', token=token)


def retry_document_processing(token, document_id):
    return _request('POST', f'/documents/{document_id}/process/retry', token=token)


def get_document(token, document_id):
    return _request('GET', f'/documents/{document_id}', token=token)


def list_project_workflows(token, project_id):
    return _request('GET', f'/projects/{project_id}/workflows', token=token)


def create_workflow(token, project_id, name):
    return _request(
        'POST',
        f'/projects/{project_id}/workflows',
        token=token,
        json={'name': name},
    )


def update_workflow(token, workflow_id, name):
    return _request(
        'PATCH',
        f'/workflows/{workflow_id}',
        token=token,
        json={'name': name},
    )


def delete_workflow(token, workflow_id):
    return _request('DELETE', f'/workflows/{workflow_id}', token=token)


def list_workflow_steps(token, workflow_id):
    return _request('GET', f'/workflows/{workflow_id}/steps', token=token)


def create_workflow_step(
    token,
    workflow_id,
    step_order,
    name,
    prompt_template,
    depends_on=None,
    condition=None,
):
    return _request(
        'POST',
        f'/workflows/{workflow_id}/steps',
        token=token,
        json={
            'step_order': step_order,
            'name': name,
            'prompt_template': prompt_template,
            'depends_on': depends_on or [],
            'condition': condition or None,
        },
    )


def delete_workflow_step(token, step_id):
    return _request('DELETE', f'/steps/{step_id}', token=token)


def run_workflow(token, workflow_id, user_input):
    # Backend creates the run, enqueues a Celery task and returns 202
    # immediately -- no longer waits for the whole workflow to finish.
    return _request(
        'POST',
        f'/workflows/{workflow_id}/run',
        token=token,
        json={'input': user_input},
    )


def cancel_workflow_run(token, run_id):
    return _request('POST', f'/runs/{run_id}/cancel', token=token)


def resume_workflow_run(token, run_id):
    return _request('POST', f'/runs/{run_id}/resume', token=token)


def retry_workflow_run(token, run_id):
    return _request('POST', f'/runs/{run_id}/retry', token=token)


def list_workflow_runs(token, page=1, page_size=20, status=None, project_id=None):
    params = {
        'page': page,
        'page_size': page_size,
    }
    if status:
        params['status'] = status
    if project_id:
        params['project_id'] = project_id

    return _request('GET', f'/runs?{urlencode(params)}', token=token)


def delete_workflow_run(token, run_id):
    return _request('DELETE', f'/runs/{run_id}', token=token)


def delete_canceled_workflow_runs(token, project_id=None):
    path = '/runs/canceled'
    if project_id:
        path = f'{path}?{urlencode({"project_id": project_id})}'
    return _request('DELETE', path, token=token)


def get_workflow_run(token, run_id):
    return _request('GET', f'/runs/{run_id}', token=token)


def list_workflow_run_events(token, run_id):
    return _request('GET', f'/runs/{run_id}/events', token=token)


def get_providers(token):
    return _request('GET', '/providers', token=token)


def update_chat_provider_defaults(
    token,
    provider=None,
    model=None,
    fallback_model=None,
    base_url=None,
    api_key=None,
):
    return _request(
        'PATCH',
        '/providers/chat/defaults',
        token=token,
        json=compact_payload(
            {
                'provider': provider,
                'model': model,
                'fallback_model': fallback_model,
                'base_url': base_url,
                'api_key': api_key,
            }
        ),
    )


def update_embedding_provider_defaults(
    token,
    provider=None,
    model=None,
    dimensions=None,
    base_url=None,
    api_key=None,
):
    return _request(
        'PATCH',
        '/providers/embeddings/defaults',
        token=token,
        json=compact_payload(
            {
                'provider': provider,
                'model': model,
                'dimensions': dimensions,
                'base_url': base_url,
                'api_key': api_key,
            }
        ),
    )


def check_chat_provider_health(token, provider, model=None):
    params = {}
    if model:
        params['model'] = model
    return _request(
        'GET',
        f'/providers/chat/{provider}/health',
        token=token,
        timeout=WORKFLOW_TIMEOUT,
        params=params,
    )


def check_embedding_provider_health(token, provider, model=None, dimensions=None):
    params = {}
    if model:
        params['model'] = model
    if dimensions:
        params['dimensions'] = dimensions
    return _request(
        'GET',
        f'/providers/embeddings/{provider}/health',
        token=token,
        timeout=WORKFLOW_TIMEOUT,
        params=params,
    )


def sync_project_embeddings(token, project_id):
    # Backend enqueues a Celery task and returns 202 immediately.
    return _request(
        'POST',
        f'/projects/{project_id}/embeddings/sync',
        token=token,
    )


def cancel_project_embedding_sync(token, project_id):
    return _request('POST', f'/projects/{project_id}/embeddings/sync/cancel', token=token)


def resume_project_embedding_sync(token, project_id):
    return _request('POST', f'/projects/{project_id}/embeddings/sync/resume', token=token)


def retry_project_embedding_sync(token, project_id):
    return _request('POST', f'/projects/{project_id}/embeddings/sync/retry', token=token)


def get_project_embedding_sync_status(token, project_id):
    return _request('GET', f'/projects/{project_id}/embeddings/sync', token=token)


def rebuild_document_embeddings(token, document_id):
    # Backend enqueues a Celery task and returns 202 immediately.
    return _request(
        'POST',
        f'/documents/{document_id}/embeddings/rebuild',
        token=token,
    )


def cancel_document_embedding_rebuild(token, document_id):
    return _request('POST', f'/documents/{document_id}/embeddings/rebuild/cancel', token=token)


def resume_document_embedding_rebuild(token, document_id):
    return _request('POST', f'/documents/{document_id}/embeddings/rebuild/resume', token=token)


def retry_document_embedding_rebuild(token, document_id):
    return _request('POST', f'/documents/{document_id}/embeddings/rebuild/retry', token=token)


def compact_payload(payload):
    return {key: value for key, value in payload.items() if value is not None}
