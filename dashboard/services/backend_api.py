import os

import requests
from django.conf import settings

BASE_API_URL = os.getenv(
    'BASE_API_URL',
    getattr(settings, 'BASE_API_URL', 'http://localhost:8000'),
).rstrip('/')


def get_health():
    response = requests.get(f'{BASE_API_URL}/health', timeout=10)
    response.raise_for_status()
    return response.json()
