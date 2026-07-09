from django.contrib import messages as django_messages
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    auth_required,
    handle_api_error,
    resolve_project,
    safe_next_url,
    session_token,
)

@auth_required
@require_POST
def upload_document(request, project_slug):
    token = session_token(request)
    next_url = safe_next_url(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect(next_url or "dashboard:projects")

    uploaded_file = request.FILES.get("file")
    if not uploaded_file:
        django_messages.error(request, "Choose a document to upload.")
    else:
        try:
            document = backend_api.upload_document(token, project["id"], uploaded_file)
            backend_api.process_document(token, document["id"])
            django_messages.success(request, "Document uploaded and processed.")
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
        django_messages.success(request, "Document processed. It is ready for review.")
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


