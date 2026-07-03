import requests
from django.shortcuts import render

from .services.backend_api import BASE_API_URL, get_health


def index(request):
    backend_health = None
    backend_error = None

    try:
        backend_health = get_health()
    except requests.RequestException as exc:
        backend_error = str(exc)

    return render(
        request,
        'dashboard/index.html',
        {
            'backend_api_url': BASE_API_URL,
            'backend_health': backend_health,
            'backend_error': backend_error,
        },
    )
