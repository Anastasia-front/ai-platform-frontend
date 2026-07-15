import json
import re
import time
from functools import wraps

import requests
from django.conf import settings as django_settings
from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify

from ..services import backend_api

MAIN_ENDPOINTS = [
    {"method": "GET", "path": "/openapi.json", "area": "Docs"},
    {"method": "GET", "path": "/docs", "area": "Docs"},
    {"method": "GET", "path": "/docs/oauth2-redirect", "area": "Docs"},
    {"method": "GET", "path": "/redoc", "area": "Docs"},
    {"method": "GET", "path": "/health", "area": "Health"},
    {"method": "POST", "path": "/auth/register", "area": "Auth"},
    {"method": "POST", "path": "/auth/login", "area": "Auth"},
    {"method": "POST", "path": "/auth/google", "area": "Auth"},
    {"method": "POST", "path": "/auth/refresh", "area": "Auth"},
    {"method": "GET", "path": "/auth/me", "area": "Auth"},
    {"method": "GET", "path": "/providers", "area": "Providers"},
    {"method": "GET", "path": "/providers/config", "area": "Providers"},
    {"method": "PATCH", "path": "/providers/chat/defaults", "area": "Providers"},
    {"method": "PATCH", "path": "/providers/embeddings/defaults", "area": "Providers"},
    {"method": "GET", "path": "/providers/chat/{provider}/health", "area": "Providers"},
    {
        "method": "GET",
        "path": "/providers/embeddings/{provider}/health",
        "area": "Providers",
    },
    {"method": "GET", "path": "/projects/", "area": "Projects"},
    {"method": "POST", "path": "/projects/", "area": "Projects"},
    {"method": "GET", "path": "/projects/{project_id}", "area": "Projects"},
    {"method": "PATCH", "path": "/projects/{project_id}", "area": "Projects"},
    {"method": "DELETE", "path": "/projects/{project_id}", "area": "Projects"},
    {"method": "POST", "path": "/projects/{project_id}/retrieve", "area": "Projects"},
    {"method": "GET", "path": "/projects/{project_id}/chats", "area": "Chats"},
    {"method": "POST", "path": "/projects/{project_id}/chats", "area": "Chats"},
    {"method": "GET", "path": "/chats/{chat_id}", "area": "Chats"},
    {"method": "PATCH", "path": "/chats/{chat_id}", "area": "Chats"},
    {"method": "DELETE", "path": "/chats/{chat_id}", "area": "Chats"},
    {"method": "GET", "path": "/chats/{chat_id}/messages", "area": "Messages"},
    {"method": "POST", "path": "/chats/{chat_id}/messages", "area": "Messages"},
    {
        "method": "POST",
        "path": "/chats/{chat_id}/messages/stream",
        "area": "Messages",
    },
    {
        "method": "POST",
        "path": "/chats/messages/{message_id}/regenerate",
        "area": "Messages",
    },
    {"method": "GET", "path": "/projects/{project_id}/documents", "area": "Documents"},
    {"method": "POST", "path": "/projects/{project_id}/documents", "area": "Documents"},
    {"method": "GET", "path": "/documents/{document_id}", "area": "Documents"},
    {"method": "GET", "path": "/documents/{document_id}/chunks", "area": "Documents"},
    {"method": "DELETE", "path": "/documents/{document_id}", "area": "Documents"},
    {"method": "POST", "path": "/documents/{document_id}/process", "area": "Documents"},
    {
        "method": "POST",
        "path": "/documents/{document_id}/process/cancel",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/documents/{document_id}/process/retry",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/documents/{document_id}/embeddings/rebuild",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/documents/{document_id}/embeddings/rebuild/cancel",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/documents/{document_id}/embeddings/rebuild/resume",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/documents/{document_id}/embeddings/rebuild/retry",
        "area": "Documents",
    },
    {
        "method": "POST",
        "path": "/projects/{project_id}/embeddings/sync",
        "area": "Projects",
    },
    {
        "method": "GET",
        "path": "/projects/{project_id}/embeddings/sync",
        "area": "Projects",
    },
    {
        "method": "POST",
        "path": "/projects/{project_id}/embeddings/sync/cancel",
        "area": "Projects",
    },
    {
        "method": "POST",
        "path": "/projects/{project_id}/embeddings/sync/resume",
        "area": "Projects",
    },
    {
        "method": "POST",
        "path": "/projects/{project_id}/embeddings/sync/retry",
        "area": "Projects",
    },
    {"method": "GET", "path": "/projects/{project_id}/workflows", "area": "Workflows"},
    {"method": "POST", "path": "/projects/{project_id}/workflows", "area": "Workflows"},
    {"method": "GET", "path": "/workflows/{workflow_id}", "area": "Workflows"},
    {"method": "PATCH", "path": "/workflows/{workflow_id}", "area": "Workflows"},
    {"method": "DELETE", "path": "/workflows/{workflow_id}", "area": "Workflows"},
    {"method": "POST", "path": "/workflows/{workflow_id}/run", "area": "Workflows"},
    {
        "method": "POST",
        "path": "/workflows/{workflow_id}/runs/stream",
        "area": "Workflows",
    },
    {"method": "GET", "path": "/workflows/{workflow_id}/steps", "area": "Workflows"},
    {"method": "POST", "path": "/workflows/{workflow_id}/steps", "area": "Workflows"},
    {"method": "GET", "path": "/steps/{step_id}", "area": "Workflows"},
    {"method": "DELETE", "path": "/steps/{step_id}", "area": "Workflows"},
    {"method": "GET", "path": "/runs", "area": "Executions"},
    {"method": "GET", "path": "/runs/{run_id}", "area": "Executions"},
    {"method": "POST", "path": "/runs/{run_id}/resume", "area": "Executions"},
    {"method": "POST", "path": "/runs/{run_id}/retry", "area": "Executions"},
    {"method": "POST", "path": "/runs/{run_id}/cancel", "area": "Executions"},
    {"method": "DELETE", "path": "/runs/canceled", "area": "Executions"},
    {"method": "DELETE", "path": "/runs/{run_id}", "area": "Executions"},
    {"method": "GET", "path": "/runs/{run_id}/events", "area": "Executions"},
    {"method": "GET", "path": "/agent_runs/{agent_run_id}", "area": "Executions"},
    {"method": "POST", "path": "/agent_runs/", "area": "Executions"},
]

AGENT_MODES = [
    {"value": "assistant", "label": "Chat Assistant"},
    {"value": "project", "label": "Project Assistant"},
    {"value": "research", "label": "Research Agent"},
    {"value": "workspace", "label": "Workspace Agent"},
]

CONTRACT_REVIEW_NAME = "Contract review"
CONTRACT_REVIEW_STEPS = [
    {
        "order": 1,
        "name": "Extract key dates",
        "prompt": (
            "Read the contract below and extract all important dates, deadlines, "
            "renewal windows, termination notice dates, payment dates, and effective dates. "
            "Return a concise JSON array with name, date, and notes.\n\n"
            "{{input}}"
        ),
    },
    {
        "order": 2,
        "name": "Classify risk level",
        "prompt": (
            "Review the contract and extracted date findings. Classify the contract risk "
            "as low, medium, or high. Explain the main risk drivers briefly.\n\n"
            "Contract:\n{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
    {
        "order": 3,
        "name": "Generate summary",
        "prompt": (
            "Create a business-readable contract summary. Include parties, purpose, "
            "key obligations, payment terms, renewal or termination terms, and notable risks.\n\n"
            "Contract:\n{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
    {
        "order": 4,
        "name": "Save structured result",
        "prompt": (
            "Return ONLY valid JSON with this exact shape: \n"
            '{"key_dates":[{"name":"...","date":"...","notes":"..."}],\n'
            '"risk_level":"low|medium|high",\n"summary":"..."}. \n'
            "Use the contract and previous workflow outputs.\n\n"
            "Contract:\n{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
]

JOB_VACANCY_NAME = "Vacancy helper"
JOB_VACANCY_STEPS = [
    {
        "order": 1,
        "name": "Compare vacancy with CV",
        "prompt": (
            "Compare the job vacancy and CV below. Identify the strongest matches, "
            "missing requirements, seniority alignment, and evidence from the CV.\n\n"
            "{{input}}"
        ),
    },
    {
        "order": 2,
        "name": "Score match",
        "prompt": (
            "Using the comparison, score the candidate from 0 to 100 for this vacancy. "
            "Return a short explanation for the score.\n\n"
            "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
    {
        "order": 3,
        "name": "Generate cover letter",
        "prompt": (
            "Generate a tailored, concise cover letter for this vacancy using the CV facts. "
            "Avoid inventing experience not present in the CV.\n\n"
            "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
    {
        "order": 4,
        "name": "Save application note",
        "prompt": (
            "Return ONLY valid JSON with this exact shape: \n"
            '{"score":85,\n"comparison":"...",\n"cover_letter":"...",\n'
            '"application_note":"..."}. \n'
            "Use the vacancy, CV, and previous workflow outputs.\n\n"
            "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
        ),
    },
]


WORKFLOW_TEMPLATES = [
    {
        "key": "contract-review",
        "name": CONTRACT_REVIEW_NAME,
        "description": "Select a project document, run the workflow, and save structured dates, risk level, and summary.",
        "select_label": "Select project document",
        "output_shape": {"key_dates": [], "risk_level": "", "summary": ""},
        "steps": CONTRACT_REVIEW_STEPS,
        "form_type": "single_document",
        "hidden_from_generic_loop": True,
        "input_builder": lambda template, document: contract_review_input(document),
        "output_parser": lambda output: parse_contract_review_output(output),
    },
    {
        "key": "job-vacancy",
        "name": JOB_VACANCY_NAME,
        "description": "Compare a vacancy with a CV, score the match, generate a cover letter, and save an application note.",
        "output_shape": {
            "score": 0,
            "comparison": "",
            "cover_letter": "",
            "application_note": "",
        },
        "steps": JOB_VACANCY_STEPS,
        "form_type": "vacancy",
        "hidden_from_generic_loop": True,
        "input_builder": (
            lambda template, vacancy_link, vacancy_context, cv_document: job_vacancy_input(
                vacancy_link=vacancy_link,
                vacancy_context=vacancy_context,
                cv_document=cv_document,
            )
        ),
        "output_parser": lambda output: parse_job_vacancy_output(output),
    },
    {
        "key": "invoice-processing",
        "name": "Invoice processing",
        "description": "Extract invoice information and produce structured accounting data.",
        "select_label": "Select invoice document",
        "output_shape": {
            "vendor": "",
            "invoice_number": "",
            "invoice_date": "",
            "due_date": "",
            "currency": "",
            "subtotal": 0,
            "tax": 0,
            "total": 0,
            "warnings": [],
            "summary": "",
        },
        "steps": [
            {
                "order": 1,
                "name": "Extract vendor & invoice fields",
                "prompt": (
                    "Extract the vendor name, invoice number, invoice date, due date, "
                    "currency, subtotal, tax, and total from the invoice below.\n\n{{input}}"
                ),
            },
            {
                "order": 2,
                "name": "Validate totals & dates",
                "prompt": (
                    "Validate that subtotal plus tax equals total and that all dates are "
                    "consistent and well-formed. Note any discrepancies.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Detect missing information",
                "prompt": (
                    "List any missing or inconsistent invoice fields as warnings.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Generate accounting summary",
                "prompt": (
                    "Write a short accounting summary of this invoice.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 5,
                "name": "Save structured invoice",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"vendor":"...","invoice_number":"...","invoice_date":"...",'
                    '"due_date":"...","currency":"...","subtotal":0,"tax":0,"total":0,'
                    '"warnings":["..."],"summary":"..."}. \n'
                    "Use the invoice and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
    {
        "key": "meeting-minutes",
        "name": "Meeting minutes generator",
        "description": "Turn a meeting transcript into actionable notes.",
        "select_label": "Select transcript document",
        "output_shape": {
            "summary": "",
            "decisions": [],
            "action_items": [],
            "participants": [],
            "deadlines": [],
        },
        "steps": [
            {
                "order": 1,
                "name": "Extract key discussion points",
                "prompt": (
                    "Extract the key discussion points from the meeting transcript below.\n\n{{input}}"
                ),
            },
            {
                "order": 2,
                "name": "Identify decisions",
                "prompt": (
                    "Identify all decisions made during the meeting.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Extract action items",
                "prompt": (
                    "Extract action items from the meeting.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Assign responsibilities",
                "prompt": (
                    "Assign a responsible participant and deadline (if mentioned) to each action item.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 5,
                "name": "Save meeting summary",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"summary":"...","decisions":["..."],"action_items":["..."],'
                    '"participants":["..."],"deadlines":["..."]}. \n'
                    "Use the transcript and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
    {
        "key": "email-processing",
        "name": "Email processing assistant",
        "description": "Process long email threads into a summary, reply, and follow-ups.",
        "select_label": "Select email thread document",
        "output_shape": {
            "summary": "",
            "reply": "",
            "tasks": [],
            "questions": [],
        },
        "steps": [
            {
                "order": 1,
                "name": "Summarize conversation",
                "prompt": "Summarize the email thread below.\n\n{{input}}",
            },
            {
                "order": 2,
                "name": "Extract questions",
                "prompt": (
                    "Extract all open questions raised in the thread.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Draft reply",
                "prompt": (
                    "Draft a concise reply addressing the open questions.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Identify follow-up tasks",
                "prompt": (
                    "Identify any follow-up tasks implied by the thread.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 5,
                "name": "Save structured result",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"summary":"...","reply":"...","tasks":["..."],"questions":["..."]}. \n'
                    "Use the thread and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
    {
        "key": "requirements-to-tasks",
        "name": "Requirements to development tasks",
        "description": "Turn requirements into an estimated development backlog.",
        "select_label": "Select requirements document",
        "output_shape": {
            "epics": [],
            "stories": [],
            "technical_tasks": [],
            "risks": [],
            "summary": "",
        },
        "steps": [
            {
                "order": 1,
                "name": "Extract functional requirements",
                "prompt": (
                    "Extract the functional requirements from the document below.\n\n{{input}}"
                ),
            },
            {
                "order": 2,
                "name": "Extract technical requirements",
                "prompt": (
                    "Extract the technical requirements and constraints.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Generate development tasks",
                "prompt": (
                    "Generate epics, stories, and technical tasks covering the requirements.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Estimate complexity",
                "prompt": (
                    "Estimate complexity and highlight delivery risks for the generated tasks.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 5,
                "name": "Save backlog",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"epics":["..."],"stories":["..."],"technical_tasks":["..."],'
                    '"risks":["..."],"summary":"..."}. \n'
                    "Use the requirements and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
    {
        "key": "sop-generator",
        "name": "SOP / Process generator",
        "description": "Turn a process description into internal SOP documentation.",
        "select_label": "Select process description document",
        "output_shape": {
            "purpose": "",
            "steps": [],
            "risks": [],
            "recommendations": [],
            "summary": "",
        },
        "steps": [
            {
                "order": 1,
                "name": "Identify workflow stages",
                "prompt": (
                    "Identify the distinct stages of the process described below.\n\n{{input}}"
                ),
            },
            {
                "order": 2,
                "name": "Generate SOP",
                "prompt": (
                    "Generate a standard operating procedure covering the purpose and steps.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Highlight risks",
                "prompt": (
                    "Highlight the operational risks in this process.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Suggest improvements",
                "prompt": (
                    "Suggest improvements to the process.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 5,
                "name": "Save documentation",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"purpose":"...","steps":["..."],"risks":["..."],'
                    '"recommendations":["..."],"summary":"..."}. \n'
                    "Use the process description and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
    {
        "key": "resume-screening",
        "name": "Resume screening",
        "description": "Evaluate and rank candidate CVs against a job description.",
        "multi_doc": True,
        "output_shape": {
            "ranked_candidates": [],
            "interview_questions": [],
            "recommendation": "",
        },
        "steps": [
            {
                "order": 1,
                "name": "Evaluate candidates",
                "prompt": (
                    "Evaluate each candidate CV against the job description below.\n\n{{input}}"
                ),
            },
            {
                "order": 2,
                "name": "Rank candidates",
                "prompt": (
                    "Rank the candidates from strongest to weakest fit, with reasoning.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 3,
                "name": "Generate interview questions",
                "prompt": (
                    "Generate targeted interview questions based on the candidate gaps found.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
            {
                "order": 4,
                "name": "Save shortlist",
                "prompt": (
                    "Return ONLY valid JSON with this exact shape: \n"
                    '{"ranked_candidates":["..."],"interview_questions":["..."],'
                    '"recommendation":"..."}. \n'
                    "Use the job description, CVs, and previous workflow outputs.\n\n"
                    "{{input}}\n\nPrevious outputs:\n{{dependency_outputs}}"
                ),
            },
        ],
    },
]


def session_token(request):
    return request.session.get("access_token")


def refresh_session_token(request):
    refresh_token = request.session.get("refresh_token")
    if not refresh_token:
        return False

    try:
        token_payload = backend_api.refresh_token(refresh_token)
    except backend_api.BackendAPIError:
        request.session.pop("access_token", None)
        request.session.pop("refresh_token", None)
        return False

    store_login_session(
        request,
        token_payload,
        fallback_email=request.session.get("user", {}).get("email", ""),
        refresh_user=False,
    )
    return True


def refresh_session_token_if_needed(request):
    if not session_token(request):
        return refresh_session_token(request)

    refreshed_at = request.session.get("access_token_refreshed_at")
    expires_in = request.session.get("access_token_expires_in", 1800)
    if refreshed_at is None:
        request.session["access_token_refreshed_at"] = time.time()
        request.session["access_token_expires_in"] = expires_in
        return True

    try:
        refresh_after = float(refreshed_at) + max(60, int(expires_in) - 120)
    except (TypeError, ValueError):
        return refresh_session_token(request)

    if time.time() >= refresh_after:
        return refresh_session_token(request)
    return True


def auth_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not refresh_session_token_if_needed(request):
            return redirect(f"{reverse('dashboard:login')}?next={request.path}")
        return view_func(request, *args, **kwargs)

    return wrapped


def app_context(
    request, active_project_slug=None, active_chat_slug=None, endpoints=None
):
    token = session_token(request)
    projects_payload = []
    projects_error = None

    if token:
        try:
            projects_payload = with_slugs(backend_api.list_projects(token), "name")
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            projects_error = exc.message

    return {
        "backend_api_url": backend_api.BASE_API_URL,
        "current_user": request.session.get("user"),
        "projects": projects_payload,
        "projects_error": projects_error,
        "active_project_slug": active_project_slug,
        "active_chat_slug": active_chat_slug,
        "current_url_name": (
            request.resolver_match.url_name if request.resolver_match else ""
        ),
        "endpoints": endpoints or [],
        "agent_modes": AGENT_MODES,
    }


def render_auth(request, template_name):
    return render(
        request,
        template_name,
        {
            "backend_api_url": backend_api.BASE_API_URL,
            "google_client_id": django_settings.GOOGLE_CLIENT_ID,
            "google_oauth_enabled": google_oauth_enabled(),
        },
    )


def token_refresh_context(request):
    return {
        "has_refresh_token": bool(request.session.get("refresh_token")),
        "access_token_expires_in": request.session.get("access_token_expires_in", 1800),
    }


def google_oauth_enabled():
    return bool(
        django_settings.GOOGLE_CLIENT_ID and django_settings.GOOGLE_CLIENT_SECRET
    )


def google_redirect_uri(request):
    return request.build_absolute_uri(reverse("dashboard:google_login_callback"))


def exchange_google_code(request, code):
    response = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": django_settings.GOOGLE_CLIENT_ID,
            "client_secret": django_settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": google_redirect_uri(request),
            "grant_type": "authorization_code",
        },
        timeout=backend_api.REQUEST_TIMEOUT,
    )
    if not response.ok:
        try:
            payload = response.json()
            detail = payload.get("error_description") or payload.get("error")
        except ValueError:
            detail = response.text
        raise backend_api.BackendAPIError(
            f"Google token exchange failed: {detail or response.status_code}"
        )
    return response.json()


def store_login_session(request, token_payload, fallback_email="", refresh_user=True):
    request.session["access_token"] = token_payload["access_token"]
    if token_payload.get("refresh_token"):
        request.session["refresh_token"] = token_payload["refresh_token"]
    request.session["token_type"] = token_payload.get("token_type", "bearer")
    request.session["access_token_expires_in"] = token_payload.get("expires_in") or 1800
    request.session["access_token_refreshed_at"] = time.time()
    request.session["refresh_token_expires_in"] = token_payload.get(
        "refresh_expires_in"
    )
    if refresh_user:
        try:
            request.session["user"] = backend_api.get_current_user(
                request.session["access_token"]
            )
        except backend_api.BackendAPIError:
            request.session["user"] = {"email": fallback_email}


def handle_api_error(request, exc):
    if exc.status_code == 401:
        if refresh_session_token(request):
            return
        request.session.pop("access_token", None)
        request.session.pop("refresh_token", None)
        django_messages.error(request, "Your session expired. Please log in again.")


SENSITIVE_FIELD_RE = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|authorization|"
    r"client[_-]?secret|secret|password|passwd|pwd|credential|private[_-]?key)",
    flags=re.IGNORECASE,
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|id[_-]?token|"
    r"authorization|client[_-]?secret|secret|password|passwd|pwd|credential|"
    r"private[_-]?key)\b\s*[:=]\s*)(?P<quote>['\"]?)(?P<value>[^'\"\s,&}]+)",
    flags=re.IGNORECASE,
)
ENV_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?P<prefix>\b[A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|"
    r"CREDENTIAL|PRIVATE_KEY)\b\s*[:=]\s*)(?P<quote>['\"]?)(?P<value>[^'\"\s,&}]+)"
)
QUERY_SECRET_RE = re.compile(
    r"(?P<prefix>[?&](?:key|api_key|api-key|token|access_token|auth|signature|"
    r"client_secret)=)(?P<value>[^&\s'\"}]+)",
    flags=re.IGNORECASE,
)
GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")


def redact_secrets(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if SENSITIVE_FIELD_RE.search(str(key)):
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_secrets(item)
        return redacted

    if isinstance(value, list):
        return [redact_secrets(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)

    if isinstance(value, str):
        redacted = QUERY_SECRET_RE.sub(r"\g<prefix>[redacted]", value)
        redacted = ENV_SECRET_ASSIGNMENT_RE.sub(
            lambda match: f"{match.group('prefix')}{match.group('quote')}[redacted]",
            redacted,
        )
        redacted = SECRET_ASSIGNMENT_RE.sub(
            lambda match: f"{match.group('prefix')}{match.group('quote')}[redacted]",
            redacted,
        )
        return GOOGLE_API_KEY_RE.sub("[redacted]", redacted)

    return value


def _endpoints_for(area):
    return [endpoint for endpoint in MAIN_ENDPOINTS if endpoint["area"] == area]


def safe_next_url(request):
    next_url = request.POST.get("next", "")
    if next_url.startswith("/"):
        return next_url
    return ""


def provider_page_url(request):
    project_slug = request.POST.get("project_slug", "").strip()
    if project_slug:
        return f"{reverse('dashboard:providers')}?project={project_slug}"
    return reverse("dashboard:providers")


def resource_slug(resource, field):
    value = resource.get(field, "")
    if field == "name" and value == JOB_VACANCY_NAME:
        return "job-vacancy-automation"
    return slugify(value) or "untitled"


def with_slug(resource, field):
    resource = dict(resource)
    resource["slug"] = resource_slug(resource, field)
    return resource


def with_slugs(resources, field):
    return [with_slug(resource, field) for resource in resources]


def resolve_project(token, project_slug):
    try:
        projects_payload = backend_api.list_projects(token)
    except backend_api.BackendAPIError as exc:
        return None, exc.message

    for project in projects_payload:
        if resource_slug(project, "name") == project_slug:
            return project, None

    return None, "Project not found."


def resolve_chat(token, project_id, chat_slug):
    try:
        chats_payload = backend_api.list_project_chats(token, project_id)
    except backend_api.BackendAPIError as exc:
        return None, exc.message

    for chat in chats_payload:
        if resource_slug(chat, "title") == chat_slug:
            return chat, None

    return None, "Chat not found."


def resolve_project_workflow(token, project_slug, workflow_slug):
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        return None, None, project_error

    try:
        workflows_payload = backend_api.list_project_workflows(token, project["id"])
    except backend_api.BackendAPIError as exc:
        return project, None, exc.message

    for workflow in workflows_payload:
        if resource_slug(workflow, "name") == workflow_slug:
            return project, workflow, None

    return project, None, "Workflow not found."


def find_contract_review_workflow(workflows):
    return find_workflow_by_name(workflows, CONTRACT_REVIEW_NAME)


def find_job_vacancy_workflow(workflows):
    return find_workflow_by_name(workflows, JOB_VACANCY_NAME)


def find_workflow_template(template_key):
    return next(
        (template for template in WORKFLOW_TEMPLATES if template["key"] == template_key),
        None,
    )


def find_workflow_by_name(workflows, name):
    return next(
        (
            workflow
            for workflow in workflows
            if resource_slug(workflow, "name") == resource_slug({"name": name}, "name")
        ),
        None,
    )


def find_document(documents, document_id):
    return next(
        (
            item
            for item in documents
            if document_id and str(item.get("id")) == str(document_id)
        ),
        None,
    )


def contract_review_input(document):
    return (
        "Contract review REQUEST\n\n"
        f"Document filename: {document.get('filename', 'contract')}\n\n"
        "Analyze this contract using the workflow steps. The final output must be valid JSON "
        "with key_dates, risk_level, and summary.\n\n"
        "CONTRACT TEXT\n"
        f"{document.get('text', '')}"
    )


def job_vacancy_input(vacancy_link, vacancy_context, cv_document):
    return (
        "Vacancy helper REQUEST\n\n"
        f"Vacancy link: {vacancy_link}\n"
        f"CV filename: {cv_document.get('filename', 'cv')}\n\n"
        "The final output must be valid JSON with score, comparison, cover_letter, "
        "and application_note.\n\n"
        "VACANCY LINK\n"
        f"{vacancy_link}\n\n"
        "DEDICATED LOGIC INPUT\n"
        f"{vacancy_context or 'No additional vacancy instructions provided.'}\n\n"
        "CV TEXT\n"
        f"{cv_document.get('text', '')}"
    )


def parse_contract_review_output(output):
    parsed = parse_json_object(output)
    if isinstance(parsed, dict):
        summary = parsed.get("summary")
        nested_summary = (
            parse_json_object(summary) if isinstance(summary, str) else None
        )
        if isinstance(nested_summary, dict):
            parsed = {
                **nested_summary,
                **{key: value for key, value in parsed.items() if value},
            }
            summary = parsed.get("summary")

        return {
            "key_dates": normalize_key_dates(parsed.get("key_dates")),
            "risk_level": parsed.get("risk_level") or "Not specified",
            "summary": normalize_summary(summary),
        }

    return {
        "key_dates": [],
        "risk_level": extract_risk_level(output),
        "summary": output.strip() or "No summary returned.",
    }


def parse_job_vacancy_output(output):
    parsed = parse_json_object(output)
    if isinstance(parsed, dict):
        comparison = normalize_job_vacancy_comparison(parsed.get("comparison"))
        return {
            "score": normalize_score(parsed.get("score")),
            "comparison": comparison["summary"],
            "strong_matches": comparison["strong_matches"],
            "missing_requirements": comparison["missing_requirements"],
            "seniority_alignment": comparison["seniority_alignment"],
            "cover_letter": normalize_summary(parsed.get("cover_letter")),
            "application_note": normalize_summary(parsed.get("application_note")),
        }

    return {
        "score": extract_score(output),
        "comparison": output.strip() or "No comparison returned.",
        "strong_matches": [],
        "missing_requirements": [],
        "seniority_alignment": {},
        "cover_letter": "No cover letter returned.",
        "application_note": "No application note returned.",
    }


def generic_template_input(template, document):
    return (
        f"{template['name']} REQUEST\n\n"
        f"Document filename: {document.get('filename', 'document')}\n\n"
        "Process this document using the workflow steps. The final output must be valid "
        f"JSON with this shape: {json.dumps(template['output_shape'])}.\n\n"
        "DOCUMENT TEXT\n"
        f"{document.get('text', '')}"
    )


def resume_screening_input(template, job_description, cv_documents):
    cv_sections = "\n\n".join(
        f"CV filename: {cv.get('filename', 'cv')}\n{cv.get('text', '')}"
        for cv in cv_documents
    )
    return (
        f"{template['name']} REQUEST\n\n"
        f"Job description filename: {job_description.get('filename', 'job description')}\n\n"
        "Evaluate all candidate CVs against the job description. The final output must be "
        f"valid JSON with this shape: {json.dumps(template['output_shape'])}.\n\n"
        f"JOB DESCRIPTION\n{job_description.get('text', '')}\n\n"
        f"CANDIDATE CVS\n{cv_sections}"
    )


def parse_generic_template_output(output, output_shape):
    parsed = parse_json_object(output)
    result = dict(output_shape)
    if isinstance(parsed, dict):
        for key in output_shape:
            if key in parsed and parsed[key] not in (None, ""):
                result[key] = parsed[key]
        return result

    for key, default in output_shape.items():
        if isinstance(default, str):
            result[key] = output.strip() or "No output returned."
            break
    return result


def build_template_result_rows(structured):
    rows = []
    for key, value in structured.items():
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            if value and isinstance(value[0], dict):
                rows.append({"label": label, "type": "list_of_dicts", "items": value})
            else:
                rows.append(
                    {"label": label, "type": "list", "items": [str(item) for item in value]}
                )
        elif isinstance(value, dict):
            rows.append({"label": label, "type": "dict", "items": value})
        else:
            rows.append(
                {
                    "label": label,
                    "type": "text",
                    "value": str(value) if value not in (None, "") else "Not specified",
                }
            )
    return rows


def parse_json_object(value):
    if not value:
        return None

    candidates = [str(value).strip()]
    fenced_blocks = re.findall(
        r"```(?:json)?\s*(.*?)```",
        str(value),
        flags=re.DOTALL | re.IGNORECASE,
    )
    candidates.extend(block.strip() for block in fenced_blocks)
    candidates.extend(repair_jsonish_candidate(candidate) for candidate in list(candidates))

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    for candidate in candidates:
        for index, character in enumerate(candidate):
            if character != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    return None


def repair_jsonish_candidate(candidate):
    repaired = []
    in_string = False
    escaped = False
    index = 0

    while index < len(candidate):
        character = candidate[index]
        next_character = candidate[index + 1] if index + 1 < len(candidate) else ""

        if in_string:
            repaired.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue

        if character == "\\" and next_character == "n":
            repaired.append("\n")
            index += 2
            continue

        if character == "\\" and next_character == '"':
            repaired.append('"')
            in_string = True
            index += 2
            continue

        repaired.append(character)
        if character == '"':
            in_string = True
        index += 1

    return "".join(repaired)


def normalize_summary(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2)
    return str(value).strip() if value else "No summary returned."


def normalize_score(value):
    if isinstance(value, (int, float)):
        return max(0, min(100, int(value)))
    match = re.search(r"\d{1,3}", str(value or ""))
    if match:
        return max(0, min(100, int(match.group(0))))
    return "Not specified"


def extract_score(output):
    match = re.search(r"\b(\d{1,3})\s*(?:/100|%)?", output or "")
    if match:
        return max(0, min(100, int(match.group(1))))
    return "Not specified"


def normalize_key_dates(value):
    if isinstance(value, list):
        dates = []
        for item in value:
            if isinstance(item, dict):
                dates.append(
                    {
                        "name": item.get("name") or "Date",
                        "date": item.get("date") or "Not specified",
                        "notes": item.get("notes") or "",
                    }
                )
            else:
                dates.append({"name": str(item), "date": "", "notes": ""})
        return dates
    if value:
        return [{"name": str(value), "date": "", "notes": ""}]
    return []


def normalize_job_vacancy_comparison(value):
    if isinstance(value, dict):
        return {
            "summary": normalize_summary(
                value.get("summary")
                or value.get("assessment")
                or value
            ),
            "strong_matches": normalize_match_items(
                value.get("strong_matches")
                or value.get("strongest_matches")
            ),
            "missing_requirements": normalize_match_items(
                value.get("missing_requirements")
            ),
            "seniority_alignment": normalize_alignment(
                value.get("seniority_alignment")
            ),
        }

    return {
        "summary": normalize_summary(value),
        "strong_matches": [],
        "missing_requirements": [],
        "seniority_alignment": {},
    }


def normalize_match_items(value):
    if not isinstance(value, list):
        return []

    items = []
    for item in value:
        if isinstance(item, dict):
            items.append(
                {
                    "area": normalize_summary(
                        item.get("area") or item.get("category")
                    ),
                    "details": normalize_summary(
                        item.get("details") or item.get("description")
                    ),
                    "evidence": normalize_summary(
                        item.get("evidence")
                        or item.get("evidence_cv")
                        or item.get("evidence_job")
                    ),
                }
            )
        elif item:
            items.append({"area": normalize_summary(item), "details": "", "evidence": ""})
    return items


def normalize_alignment(value):
    if not isinstance(value, dict):
        return {}

    return {
        "alignment": normalize_summary(
            value.get("alignment") or value.get("assessment")
        ),
        "details": normalize_summary(
            value.get("details") or value.get("assessment")
        ),
        "evidence": normalize_summary(
            value.get("evidence")
            or value.get("evidence_cv")
            or value.get("evidence_job")
        ),
    }
def extract_risk_level(output):
    match = re.search(r"\b(low|medium|high)\b", output or "", flags=re.IGNORECASE)
    return match.group(1).lower() if match else "Not specified"


def summarize_workflow_run(workflow_run, events):
    output = workflow_run.get("output") or ""
    template_type = workflow_template_type(workflow_run, output)
    template = find_workflow_template(template_type)
    if template and template.get("output_parser"):
        structured = template["output_parser"](output)
    elif template:
        structured = parse_generic_template_output(output, template["output_shape"])
    else:
        structured = parse_contract_review_output(output)

    event_counts = {}
    for event in events:
        event_type = event.get("event_type") or "event"
        event_counts[event_type] = event_counts.get(event_type, 0) + 1

    return {
        "template_type": template_type,
        "template_name": template["name"] if template else None,
        "output": output,
        "structured": structured,
        "rows": build_template_result_rows(structured),
        "input_source": execution_input_source(workflow_run.get("input") or ""),
        "input_sources": execution_input_sources(workflow_run.get("input") or ""),
        "event_counts": event_counts,
        "event_count": len(events),
    }


INPUT_SOURCE_LABELS = (
    "Document filename",
    "Job description filename",
    "Vacancy link",
    "CV filename",
)


def execution_input_sources(run_input):
    sources = []
    for label in INPUT_SOURCE_LABELS:
        values = [
            match.strip()
            for match in re.findall(
                rf"^{re.escape(label)}:\s*(.+)$",
                run_input,
                flags=re.MULTILINE,
            )
            if match.strip()
        ]
        if values:
            sources.append(
                {
                    "label": label,
                    "value": ", ".join(values),
                    "values": values,
                }
            )
    return sources


def execution_input_source(run_input):
    sources = execution_input_sources(run_input)
    if sources:
        first = sources[0]
        return f"{first['label']}: {first['value']}"
    return None


def workflow_template_type(workflow_run, output):
    run_input = workflow_run.get("input") or ""
    workflow_name = workflow_run.get("workflow_name") or workflow_run.get("name") or ""
    source = f"{workflow_name}\n{run_input}\n{output}".lower()

    for template in WORKFLOW_TEMPLATES:
        if template["name"].lower() in source:
            return template["key"]

    parsed = parse_json_object(output)
    if isinstance(parsed, dict):
        for template in WORKFLOW_TEMPLATES:
            if set(template["output_shape"].keys()) & set(parsed.keys()):
                return template["key"]

    return "contract-review"


def workflow_projects_by_id(token, projects):
    workflow_project_map = {}
    for project in projects:
        try:
            workflows_payload = backend_api.list_project_workflows(token, project["id"])
        except backend_api.BackendAPIError:
            continue

        for workflow in workflows_payload:
            workflow_project_map[workflow.get("id")] = {
                "id": project.get("id"),
                "name": project.get("name", "Project"),
                "slug": project.get("slug") or resource_slug(project, "name"),
            }

    return workflow_project_map


def workflow_url(project, workflow):
    return (
        f"{reverse('dashboard:workflows')}"
        f"?project={resource_slug(project, 'name')}&workflow={resource_slug(workflow, 'name')}"
    )


def workflow_template_url(project, workflow, template):
    return f"{workflow_url(project, workflow)}&template={template}"


def parse_depends_on(value):
    if not value.strip():
        return []

    return [int(item.strip()) for item in value.split(",") if item.strip()]
