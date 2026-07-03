import os

import requests
from django.conf import settings

BASE_API_URL = os.getenv(
    'BASE_API_URL',
    getattr(settings, 'BASE_API_URL', 'http://localhost:8000'),
).rstrip('/')
BASE_API_TOKEN = os.getenv('BASE_API_TOKEN', '')
REQUEST_TIMEOUT = 10


class BackendAPIError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _headers():
    if not BASE_API_TOKEN:
        return {}

    return {
        'Authorization': f'Bearer {BASE_API_TOKEN}',
    }


def _request(method, path, **kwargs):
    url = f'{BASE_API_URL}{path}'
    try:
        response = requests.request(
            method,
            url,
            headers=_headers(),
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

    return ''


def get_health():
    return _request('GET', '/health')


def list_projects():
    return _request('GET', '/projects/')


def get_project(project_id):
    return _request('GET', f'/projects/{project_id}')


def list_project_workflows(project_id):
    return _request('GET', f'/projects/{project_id}/workflows')


def list_project_documents(project_id):
    return _request('GET', f'/projects/{project_id}/documents')
