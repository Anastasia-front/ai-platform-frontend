from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    auth_required,
    handle_api_error,
    resolve_project,
    resource_slug,
    safe_next_url,
    session_token,
)

# Statuses for which the frontend should keep polling for an updated
# status; anything else (indexed/failed) is terminal.
ACTIVE_DOCUMENT_STATUSES = {"queued", "processing", "cancelling"}

@auth_required
@require_POST
def upload_document(request, project_slug):
    token = session_token(request)
    next_url = safe_next_url(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    uploaded_files = request.FILES.getlist("file")
    if not uploaded_files:
        django_messages.error(request, "Choose at least one document to upload.")
    else:
        uploaded_count = 0
        try:
            for uploaded_file in uploaded_files:
                document = backend_api.upload_document(
                    token,
                    project["id"],
                    uploaded_file,
                )
                backend_api.process_document(token, document["id"])
                uploaded_count += 1

            django_messages.success(
                request,
                (
                    "Document uploaded and queued for processing."
                    if uploaded_count == 1
                    else f"{uploaded_count} documents uploaded and queued for processing."
                ),
            )
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            django_messages.error(request, exc.message)

    return redirect(
        next_url
        or reverse(
            "dashboard:project_detail",
            kwargs={"project_slug": resource_slug(project, "name")},
        )
    )


@auth_required
@require_POST
def delete_document(request, project_slug, document_id):
    next_url = safe_next_url(request)
    project, project_error = resolve_project(session_token(request), project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    try:
        backend_api.delete_document(session_token(request), document_id)
        django_messages.success(request, "Document deleted.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        next_url
        or reverse(
            "dashboard:project_detail",
            kwargs={"project_slug": resource_slug(project, "name")},
        )
    )


@auth_required
@require_POST
def process_document(request, project_slug, document_id):
    next_url = safe_next_url(request)
    project, project_error = resolve_project(session_token(request), project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    try:
        backend_api.process_document(session_token(request), document_id)
        django_messages.success(
            request, "Document queued for processing. It will update automatically."
        )
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        next_url
        or reverse(
            "dashboard:project_detail",
            kwargs={"project_slug": resource_slug(project, "name")},
        )
    )


@auth_required
@require_POST
def cancel_document_processing(request, project_slug, document_id):
    next_url = safe_next_url(request)
    project, project_error = resolve_project(session_token(request), project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    try:
        backend_api.cancel_document_processing(session_token(request), document_id)
        django_messages.success(request, "Document processing stopped.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        next_url
        or reverse(
            "dashboard:project_detail",
            kwargs={"project_slug": resource_slug(project, "name")},
        )
    )


@auth_required
@require_POST
def retry_document_processing(request, project_slug, document_id):
    next_url = safe_next_url(request)
    project, project_error = resolve_project(session_token(request), project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    try:
        backend_api.retry_document_processing(session_token(request), document_id)
        django_messages.success(request, "Document processing retry queued.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        next_url
        or reverse(
            "dashboard:project_detail",
            kwargs={"project_slug": resource_slug(project, "name")},
        )
    )


@auth_required
def document_status_partial(request, document_id):
    """HTMX polling target: returns just the status badge fragment for a
    single document. Navigation/reload never affects the Celery worker --
    this view only reads current status from the backend (Postgres via the
    API), it never re-triggers processing. Ownership is enforced by the
    backend (JWT-scoped), so no project lookup is needed here."""
    token = session_token(request)

    try:
        document = backend_api.get_document(token, document_id)
    except backend_api.BackendAPIError:
        document = None

    return render(
        request,
        "dashboard/partials/document_status.html",
        {"document": document, "active_statuses": ACTIVE_DOCUMENT_STATUSES},
    )


@auth_required
def document_actions_partial(request, project_slug, document_id):
    """HTMX polling target: returns the action buttons (Stop/Process/Retry)
    for a single document, so they stay in sync with the status badge
    instead of freezing at whatever state was rendered on page load."""
    token = session_token(request)

    try:
        document = backend_api.get_document(token, document_id)
    except backend_api.BackendAPIError:
        document = None

    return render(
        request,
        "dashboard/partials/document_actions_live.html",
        {
            "document": document,
            "project_slug": project_slug,
            "active_statuses": ACTIVE_DOCUMENT_STATUSES,
            "next": request.GET.get("next") or "",
        },
    )
