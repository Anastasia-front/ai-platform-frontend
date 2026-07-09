import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings as django_settings
from django.contrib import messages as django_messages
from django.shortcuts import redirect

from ..services import backend_api
from .utils import (
    exchange_google_code,
    google_oauth_enabled,
    google_redirect_uri,
    render_auth,
    session_token,
    store_login_session,
)


def index(request):
    if session_token(request):
        return redirect("dashboard:projects")
    return redirect("dashboard:login")


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        try:
            token_payload = backend_api.login(email, password)
            store_login_session(request, token_payload, fallback_email=email)
            return redirect(request.GET.get("next") or "dashboard:projects")
        except backend_api.BackendAPIError as exc:
            django_messages.error(request, exc.message)

    return render_auth(request, "dashboard/auth/login.html")


def google_login_start(request):
    if not google_oauth_enabled():
        django_messages.error(request, "Google login is not configured.")
        return redirect("dashboard:login")

    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    next_url = request.GET.get("next")
    if next_url and next_url.startswith("/"):
        request.session["google_oauth_next"] = next_url

    params = {
        "client_id": django_settings.GOOGLE_CLIENT_ID,
        "redirect_uri": google_redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}")


def google_login_callback(request):
    if not google_oauth_enabled():
        django_messages.error(request, "Google login is not configured.")
        return redirect("dashboard:login")

    if request.GET.get("error"):
        django_messages.error(
            request,
            request.GET.get("error_description") or "Google login was cancelled.",
        )
        return redirect("dashboard:login")

    state = request.GET.get("state", "")
    expected_state = request.session.pop("google_oauth_state", "")
    if not state or state != expected_state:
        django_messages.error(
            request, "Google login state did not match. Please try again."
        )
        return redirect("dashboard:login")

    code = request.GET.get("code", "")
    if not code:
        django_messages.error(request, "Google did not return an authorization code.")
        return redirect("dashboard:login")

    try:
        google_payload = exchange_google_code(request, code)
        token_payload = backend_api.google_login(google_payload["id_token"])
        store_login_session(request, token_payload)
        return redirect(
            request.session.pop("google_oauth_next", "") or "dashboard:projects"
        )
    except (KeyError, requests.RequestException, backend_api.BackendAPIError) as exc:
        if isinstance(exc, backend_api.BackendAPIError):
            message = exc.message
        else:
            message = "Google login failed. Please try again."
        django_messages.error(request, message)
        return redirect("dashboard:login")


def register_view(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        try:
            backend_api.register(email, password)
            django_messages.success(request, "Account created. You can log in now.")
            return redirect("dashboard:login")
        except backend_api.BackendAPIError as exc:
            django_messages.error(request, exc.message)

    return render_auth(request, "dashboard/auth/register.html")


def logout_view(request):
    request.session.flush()
    return redirect("dashboard:login")
