import os

import requests
from django.conf import settings

BASE_API_URL = os.getenv(
    'BASE_API_URL',
    getattr(settings, 'BASE_API_URL', 'http://localhost:8000'),
).rstrip('/')
REQUEST_TIMEOUT = 30


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


def _request(method, path, token=None, **kwargs):
    url = f'{BASE_API_URL}{path}'
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(token),
            timeout=REQUEST_TIMEOUT,
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


def delete_chat(token, chat_id):
    return _request('DELETE', f'/chats/{chat_id}', token=token)


def list_messages(token, chat_id):
    return _request('GET', f'/chats/{chat_id}/messages', token=token)


def send_message(token, chat_id, content):
    return _request(
        'POST',
        f'/chats/{chat_id}/messages',
        token=token,
        json={'content': content},
    )


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
