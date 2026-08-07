from django.contrib import messages as django_messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ..services import backend_api
from .utils import (
    _endpoints_for,
    app_context,
    auth_required,
    handle_api_error,
    provider_page_url,
    resolve_project,
    resource_slug,
    session_token,
    with_slug,
)


def _embedding_rebuild_state(document, current_embeddings):
    status = document.get("embedding_status")
    current_provider = current_embeddings.get("provider")
    current_model = current_embeddings.get("model")
    current_dimensions = current_embeddings.get("dimensions")
    stored_provider = document.get("embedding_provider")
    stored_model = document.get("embedding_model")
    stored_dimensions = document.get("embedding_dimensions")

    if status in {"queued", "processing", "cancelling"}:
        return {"label": "Embedding in progress", "tone": "live"}

    if status == "failed":
        return {"label": "Embedding failed", "tone": "warning"}

    if status == "cancelled":
        return {"label": "No embeddings", "tone": "warning"}

    if status != "completed":
        return {"label": "No embeddings", "tone": "warning"}

    if not stored_provider or not stored_model or stored_dimensions is None:
        return {
            "label": "Provider unknown — rebuild recommended",
            "tone": "warning",
        }

    if (
        stored_provider == current_provider
        and stored_model == current_model
        and stored_dimensions == current_dimensions
    ):
        return {"label": "Current provider", "tone": "success"}

    return {"label": "Rebuild recommended", "tone": "warning"}


def _with_embedding_rebuild_state(documents, provider_data):
    current_embeddings = (provider_data or {}).get("current", {}).get("embeddings", {})
    return [
        {
            **document,
            "embedding_rebuild_state": _embedding_rebuild_state(
                document,
                current_embeddings,
            ),
        }
        for document in documents
    ]


def _build_providers_context(request):
    token = session_token(request)
    context = app_context(request, endpoints=_endpoints_for("Providers"))
    active_project = None
    documents = []
    active_embedding_document = None
    active_embedding_statuses = {"queued", "processing", "cancelling"}
    project_slug = request.GET.get("project") or (
        context["projects"][0]["slug"] if context["projects"] else ""
    )

    try:
        context["provider_data"] = backend_api.get_providers(token)
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        context["provider_error"] = exc.message

    if project_slug:
        project, project_error = resolve_project(token, project_slug)
        if project_error:
            context["provider_project_error"] = project_error
        elif not project.get("id"):
            context["provider_project_error"] = (
                "This project is missing required data and can't be loaded here."
            )
        else:
            active_project = with_slug(project, "name")
            try:
                documents = _with_embedding_rebuild_state(
                    backend_api.list_project_documents(token, project["id"]),
                    context.get("provider_data"),
                )
                active_embedding_document = next(
                    (
                        document
                        for document in documents
                        if document.get("embedding_status")
                        in active_embedding_statuses
                    ),
                    None,
                )
            except backend_api.BackendAPIError as exc:
                handle_api_error(request, exc)
                context["provider_project_error"] = exc.message

    context.update(
        {
            "active_project_slug": project_slug,
            "provider_project": active_project,
            "provider_documents": documents,
            "active_embedding_document": active_embedding_document,
            "active_embedding_statuses": active_embedding_statuses,
            "provider_health_result": request.session.pop(
                "provider_health_result", None
            ),
        }
    )
    return context


@auth_required
def providers(request):
    request.session.pop("embedding_tool_result", None)
    context = _build_providers_context(request)
    return render(request, "dashboard/utility/providers.html", context)


def _is_htmx_request(request):
    return request.headers.get("HX-Request") == "true"


@auth_required
@require_POST
def update_chat_provider(request):
    token = session_token(request)
    try:
        backend_api.update_chat_provider_defaults(
            token,
            provider=request.POST.get("provider") or None,
            model=request.POST.get("model") or None,
            fallback_model=request.POST.get("fallback_model") or "",
            base_url=request.POST.get("base_url") or None,
            api_key=request.POST.get("api_key") or None,
        )
        django_messages.success(request, "Chat provider defaults saved.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    if _is_htmx_request(request):
        return render(
            request,
            "dashboard/utility/providers.html",
            _build_providers_context(request),
        )
    return redirect(provider_page_url(request))


@auth_required
@require_POST
def update_embedding_provider(request):
    token = session_token(request)
    dimensions = request.POST.get("dimensions", "").strip()
    try:
        backend_api.update_embedding_provider_defaults(
            token,
            provider=request.POST.get("provider") or None,
            model=request.POST.get("model") or None,
            dimensions=int(dimensions) if dimensions else None,
            base_url=request.POST.get("base_url") or None,
            api_key=request.POST.get("api_key") or None,
        )
        django_messages.success(request, "Embedding provider defaults saved.")
    except ValueError:
        django_messages.error(request, "Embedding dimensions must be a number.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    if _is_htmx_request(request):
        return render(
            request,
            "dashboard/utility/providers.html",
            _build_providers_context(request),
        )
    return redirect(provider_page_url(request))


@auth_required
@require_POST
def check_provider_health(request):
    token = session_token(request)
    provider_kind = request.POST.get("kind")
    provider = request.POST.get("provider", "").strip()
    model = request.POST.get("model", "").strip()
    dimensions = request.POST.get("dimensions", "").strip()

    try:
        if provider_kind == "embedding":
            result = backend_api.check_embedding_provider_health(
                token,
                provider,
                model=model,
                dimensions=int(dimensions) if dimensions else None,
            )
        else:
            result = backend_api.check_chat_provider_health(
                token, provider, model=model
            )
        request.session["provider_health_result"] = result
    except ValueError:
        django_messages.error(request, "Embedding dimensions must be a number.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(provider_page_url(request))


@auth_required
@require_POST
def sync_embeddings(request, project_slug):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    try:
        result = backend_api.sync_project_embeddings(
            token,
            project["id"],
        )
        result["display_name"] = project["name"]
        result["result_message"] = "Project embedding sync queued."
        request.session["embedding_tool_result"] = result
        django_messages.success(request, "Project embedding sync queued.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )


@auth_required
@require_POST
def rebuild_document_embeddings(request, project_slug, document_id):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    try:
        document = backend_api.get_document(token, document_id)
        result = backend_api.rebuild_document_embeddings(
            token,
            document_id,
        )
        result["display_name"] = document.get("filename") or f"Document #{document_id}"
        result["result_message"] = "Embedding rebuild queued."
        request.session["embedding_tool_result"] = result
        django_messages.success(request, "Embedding rebuild queued.")
    except backend_api.BackendAPIError as exc:
        handle_api_error(request, exc)
        django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )


@auth_required
@require_POST
def control_project_embeddings(request, project_slug, action):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    actions = {
        "cancel": backend_api.cancel_project_embedding_sync,
        "resume": backend_api.resume_project_embedding_sync,
        "retry": backend_api.retry_project_embedding_sync,
    }
    handler = actions.get(action)
    if handler is None:
        django_messages.error(request, "Unsupported embedding action.")
    else:
        try:
            result = handler(token, project["id"])
            result["display_name"] = project["name"]
            result["result_message"] = f"Project embedding {action} queued."
            request.session["embedding_tool_result"] = result
            django_messages.success(request, f"Project embedding {action} requested.")
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )


@auth_required
@require_POST
def control_document_embeddings(request, project_slug, document_id, action):
    token = session_token(request)
    project, project_error = resolve_project(token, project_slug)
    if project_error:
        django_messages.error(request, project_error)
        return redirect("dashboard:providers")

    actions = {
        "cancel": backend_api.cancel_document_embedding_rebuild,
        "resume": backend_api.resume_document_embedding_rebuild,
        "retry": backend_api.retry_document_embedding_rebuild,
    }
    handler = actions.get(action)
    if handler is None:
        django_messages.error(request, "Unsupported embedding action.")
    else:
        try:
            document = backend_api.get_document(token, document_id)
            result = handler(token, document_id)
            result["display_name"] = document.get("filename") or f"Document #{document_id}"
            result["result_message"] = f"Document embedding {action} queued."
            request.session["embedding_tool_result"] = result
            django_messages.success(request, f"Document embedding {action} requested.")
        except backend_api.BackendAPIError as exc:
            handle_api_error(request, exc)
            django_messages.error(request, exc.message)

    return redirect(
        f"{reverse('dashboard:providers')}?project={resource_slug(project, 'name')}"
    )
